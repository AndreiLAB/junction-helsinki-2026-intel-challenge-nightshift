"""Action sources for the state machine's skills.

PolicySkill: runs an exported Studio policy (OpenVINO via physicalai InferenceModel). Chunks are predicted in a
background thread so the 30 Hz loop never waits; a new chunk replaces the queue, skipping the actions that
"happened" during inference. The verdict picks the instruction (SmolVLA: one model, text task) or the model
(ACT: one model per skill). done() is a simple CPU check per skill (arm reached / gripper opened and settled).
"""
from __future__ import annotations

import threading
import time
from collections import deque

import numpy as np

from cell.motion import PoseMove


def load_policy(path, device="GPU"):
    import openvino as ov
    from physicalai.inference import InferenceModel
    dev = device if device in ov.Core().available_devices else "CPU"
    t = time.perf_counter()
    m = InferenceModel(str(path), device=dev)
    return m, dev, time.perf_counter() - t


class PolicySkill:
    def __init__(self, name, model, cfg, cams=("top", "inspect", "wrist"), fps=30, log=None, done_check=None,
                 exec_horizon=None):
        self.name, self.model, self.cfg, self.fps, self.log = name, model, cfg, fps, log
        self.instruction = cfg["skills"][name]["instruction"]
        self.feats = [f.name for f in model.input_features]
        self.cams = [c for c in cams if f"images.{c}" in self.feats]
        self.uses_task = "task" in self.feats
        self.exec_horizon = exec_horizon        # None: use whole chunk before replanning
        self.done_check = done_check or (lambda sk, q, frames, now: False)
        self.queue: deque = deque()
        self.lock = threading.Lock()
        self.pending = False
        self.latencies: list[float] = []
        self.hold = None
        self.t0 = None
        self.q_hist: deque = deque(maxlen=fps)
        self.q_start = None
        self.record_dir = None    # if set: save what the model saw (every 3rd call) for offline checks
        self.n_calls = 0

    # -- skill protocol used by the state machine --------------------------------------------------
    def start(self, q, now):
        self.model.reset()
        with self.lock:
            self.queue.clear()
        self.pending = False
        self.hold = np.asarray(q, np.float32).copy()
        self.t0 = now
        self.q_hist.clear()
        self.q_start = np.asarray(q, np.float32).copy()

    def obs(self, q, frames):
        o = {"state": np.asarray(q, np.float32)[None]}
        for c in self.cams:
            o[f"images.{c}"] = np.ascontiguousarray(frames[c])[None]
        if self.uses_task:
            o["task"] = [self.instruction]
        return o

    def _predict(self, o, t_obs):
        self.n_calls += 1
        if self.record_dir is not None and self.n_calls % 3 == 1 and self.n_calls < 120:
            try:
                self.record_dir.mkdir(parents=True, exist_ok=True)
                np.savez_compressed(self.record_dir / f"{self.name}_{self.n_calls:03d}.npz",
                                    **{k: v for k, v in o.items() if k != "task"}, task=np.array(o.get("task", [""])))
            except Exception:  # noqa: BLE001
                pass
        try:
            t = time.perf_counter()
            chunk = np.asarray(self.model.predict_action_chunk(o), np.float32)
            dt = time.perf_counter() - t
            self.latencies.append(dt * 1000)
            skip = int(round((time.monotonic() - t_obs) * self.fps))
            acts = chunk[skip:] if skip < len(chunk) else chunk[-1:]
            if self.exec_horizon:
                acts = acts[: self.exec_horizon]
            with self.lock:
                self.queue.clear()
                self.queue.extend(acts)
        except Exception as e:  # noqa: BLE001
            if self.log:
                self.log.log(-1, self.name, "policy_error", {"error": repr(e)})
        finally:
            self.pending = False

    def step(self, q, frames, now):
        self.q_hist.append(np.asarray(q, np.float32))
        with self.lock:
            n = len(self.queue)
        refill_at = max(2, int(0.3 * self.fps))
        if not self.pending and n <= refill_at:
            self.pending = True
            threading.Thread(target=self._predict, args=(self.obs(q, frames), time.monotonic()), daemon=True).start()
        with self.lock:
            if self.queue:
                self.hold = self.queue.popleft()
        return self.hold.copy()

    def done(self, q, frames, now):
        return self.done_check(self, np.asarray(q, np.float32), frames, now)

    # helpers for done checks
    def elapsed(self, now):
        return now - self.t0

    def still(self, tol=4.0, window=15):
        """Arm roughly still over the last `window` ticks (0.5 s): small jiggle allowed."""
        if len(self.q_hist) < window:
            return False
        h = np.stack(list(self.q_hist)[-window:])
        return bool(np.max(h[:, :5].max(0) - h[:, :5].min(0)) < tol)


def pick_done(pose_inspect, near=25.0, min_s=3.0, hover_near=40.0, hover_s=2.0):
    """Done when the arm is close to the inspection pose and still, or when it has hovered roughly near it for
    hover_s (the policy can jiggle in front of the camera and never be 'still'; the scripted snap finishes)."""
    target = np.asarray(pose_inspect, np.float32)
    state = {"since": None}

    def f(sk, q, frames, now):
        if sk.elapsed(now) < 0.1:
            state["since"] = None
        d = float(np.max(np.abs(q[:4] - target[:4])))
        if d < hover_near:
            state["since"] = state["since"] or now
        else:
            state["since"] = None
        if sk.elapsed(now) <= min_s:
            return False
        return (d < near and sk.still()) or (state["since"] is not None and now - state["since"] > hover_s)
    return f


def place_done(open_delta=12.0, min_s=3.0):
    def f(sk, q, frames, now):
        opened = q[5] - sk.q_start[5] > open_delta
        return sk.elapsed(now) > min_s and opened and sk.still()
    return f


def make_policy_skills(models: dict, cfg, log=None, scripted_place=False):
    """models: skill name -> InferenceModel (same object for all three with SmolVLA).
    scripted_place: ladder (3), learned pick + taught moves for placing."""
    hz = cfg.get("run", {}).get("exec_horizon")
    if scripted_place:
        return {
            "pick_present": PolicySkill("pick_present", models["pick_present"], cfg, log=log, exec_horizon=hz,
                                        done_check=pick_done(cfg["poses"]["inspect"])),
            "place_good": ScriptedPlace(cfg["poses"]["above_good"], cfg),
            "place_defect": ScriptedPlace(cfg["poses"]["above_defect"], cfg),
        }
    return {
        "pick_present": PolicySkill("pick_present", models["pick_present"], cfg, log=log, exec_horizon=hz,
                                    done_check=pick_done(cfg["poses"]["inspect"])),
        "place_good": PolicySkill("place_good", models["place_good"], cfg, log=log, exec_horizon=hz, done_check=place_done()),
        "place_defect": PolicySkill("place_defect", models["place_defect"], cfg, log=log, exec_horizon=hz, done_check=place_done()),
    }


class ScriptedPlace:
    """Ladder fallback (3): a taught move to the bowl (up, sideways, down, grip kept), then open the gripper."""

    def __init__(self, pose, cfg, open_value=45.0):
        from cell.motion import Route, plan_route
        self.Route, self.plan_route = Route, plan_route
        self.pose, self.cfg, self.open_value = np.asarray(pose, np.float32), cfg, open_value
        sa = cfg["safety"]
        self.max_step = np.asarray(sa["max_step_per_tick"], np.float32) * float(sa["speed"])
        self.tol, self.settle_s = sa["settle_tol"], sa["settle_s"]
        self.instruction = ""
        self.route = None
        self.opening_since = None

    def start(self, q, now):
        q = np.asarray(q, np.float32)
        targets = [np.concatenate([t[:5], [q[5]]]).astype(np.float32)
                   for t in self.plan_route(q, self.pose, self.cfg["poses"].get("travel"))]
        self.route = self.Route(targets, self.max_step, self.tol, self.settle_s, keep_gripper=True)
        self.route.start(q, now)
        self.opening_since = None
        self.cmd = q.copy()

    def step(self, q, frames, now):
        if self.opening_since is None:
            self.cmd = self.route.step(q, frames, now)
            if self.route.done(q, frames, now):
                self.opening_since = now
        else:
            self.cmd = self.cmd.copy()
            self.cmd[5] = self.open_value
        return self.cmd.copy()

    def done(self, q, frames, now):
        return self.opening_since is not None and now - self.opening_since > 1.0
