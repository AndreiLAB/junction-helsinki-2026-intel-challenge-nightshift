"""Robot cell state machine. Tick-driven: call update(q, frames, now) once per control tick; it returns
the 6-joint action to send. Pure logic: robot, policy, inspector and checks are injected, so it runs
the same with fakes (mock) and with the real runtime.

States: HOME, PICK_PRESENT, SNAP_TO_INSPECT, CHECK_HELD, INSPECT, DECIDE, PLACE_GOOD, PLACE_DEFECT,
NEXT_VIEW, REGRASP, CONFIRM, DONE, FAULT.  Verdict rule: docs/CONTRACTS.md (implemented in decide()).
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field

import numpy as np

from cell.motion import Hold, PoseMove, Route, plan_route


class S(str, enum.Enum):
    HOME = "HOME"
    PICK_PRESENT = "PICK_PRESENT"
    SNAP_TO_INSPECT = "SNAP_TO_INSPECT"
    CHECK_HELD = "CHECK_HELD"
    INSPECT = "INSPECT"
    DECIDE = "DECIDE"
    PLACE_GOOD = "PLACE_GOOD"
    PLACE_DEFECT = "PLACE_DEFECT"
    NEXT_VIEW = "NEXT_VIEW"
    REGRASP = "REGRASP"
    CONFIRM = "CONFIRM"
    DONE = "DONE"
    FAULT = "FAULT"


GOOD, DEFECT, UNCERTAIN, NO_BRICK = "GOOD", "DEFECT", "UNCERTAIN", "NO_BRICK"
VIEW_POSES = ["inspect", "inspect_view2", "inspect_view3"]


def decide(view_scores: list[float], t_low: float, t_high: float) -> tuple[str, float]:
    """Contract rule: score = max over views; < t_low GOOD; > t_high DEFECT; else UNCERTAIN."""
    score = max(view_scores)
    if score < t_low:
        return GOOD, score
    if score > t_high:
        return DEFECT, score
    return UNCERTAIN, score


@dataclass
class Brick:
    idx: int
    pick_attempts: int = 0          # pick_present runs for this brick
    regrasps: int = 0
    views: list = field(default_factory=list)   # [{view, score}]
    verdict: str | None = None
    final: str | None = None        # GOOD / DEFECT / SKIPPED


class CellStateMachine:
    def __init__(self, cfg: dict, skills: dict, inspector, checks, log, max_bricks: int | None = None,
                 on_put_back=None):
        self.cfg = cfg
        self.on_put_back = on_put_back   # mock only: tell the fake world the brick is back on the plate
        self.skills = skills            # name -> skill with start(q, now, instruction) / step / done
        self.inspector = inspector
        self.checks = checks
        self.log = log
        sa = cfg["safety"]
        self.max_step = np.asarray(sa["max_step_per_tick"], np.float32) * float(sa["speed"])
        self.tol, self.settle_s = sa["settle_tol"], sa["settle_s"]
        ins = cfg["inspection"]
        self.t_low, self.t_high = ins["t_low"], ins["t_high"]
        self.max_views, self.inspect_timeout = ins["max_views"], ins["timeout_s"]
        run = cfg["run"]
        self.max_bricks = max_bricks or run["max_bricks"]
        self.max_pick_attempts, self.max_regrasps = run["max_pick_attempts"], run["max_regrasps"]
        self.pick_near_inspect = float(run.get("pick_near_inspect", 40.0))
        self.release_open = float(run.get("release_open", 40.0))
        self.release_s = float(run.get("release_s", 1.0))
        self.skill_cfg = cfg["skills"]
        self.poses = cfg["poses"]

        self.state = S.HOME
        self.brick = Brick(0)
        self.results: list[Brick] = []
        self.ctrl = None                 # current motion/skill controller
        self.t_state = None
        self.timeout = None
        self.last_cmd = None
        self.before_place = None         # top-view snapshot for CONFIRM
        self.fault_reason = None
        self.counters = {"timeouts": 0, "no_brick": 0, "uncertain": 0, "regrasps": 0, "unconfirmed": 0}

    # ---- helpers -------------------------------------------------------------------------------
    @property
    def finished(self) -> bool:
        return self.state in (S.DONE, S.FAULT)

    def _ev(self, event, data=None, now=None):
        self.log.log(self.brick.idx, self.state.value, event, data, ts=None)

    def _enter(self, state: S, q, now, ctrl=None, timeout=None, **data):
        self.state = state
        self.t_state = now
        self.ctrl = ctrl
        self.timeout = timeout
        if ctrl is not None and hasattr(ctrl, "start"):
            ctrl.start(q, now)
        self._ev("enter", data or None)

    def _move(self, state, pose_name, q, now):
        keep = pose_name in VIEW_POSES
        targets = plan_route(q, self.poses[pose_name], self.poses.get("travel"))
        if keep:  # holding a brick: never change the grip on the way
            targets = [np.concatenate([t[:5], [q[5]]]).astype(np.float32) for t in targets]
        mv = Route(targets, self.max_step, self.tol, self.settle_s, keep_gripper=keep)
        self._enter(state, q, now, mv, self.skill_cfg["scripted_move_timeout_s"], pose=pose_name)

    def _skill(self, state, name, q, now):
        sk = self.skills[name]
        sk.instruction = self.skill_cfg[name]["instruction"]
        self._enter(state, q, now, sk, self.skill_cfg[name]["timeout_s"], skill=name,
                    instruction=sk.instruction)

    def _hold(self, state, q, now, timeout=None, **data):
        self._enter(state, q, now, Hold(self.last_cmd if self.last_cmd is not None else q), timeout, **data)

    def _timed_out(self, now):
        return self.timeout is not None and now - self.t_state > self.timeout

    def fault(self, reason, q, now):
        self.fault_reason = reason
        self._ev("fault", {"reason": reason})
        self._hold(S.FAULT, q, now, reason=reason)

    def _next_brick(self, q, now, final):
        self.brick.final = final
        self.results.append(self.brick)
        self._ev("brick_done", {"final": final, "verdict": self.brick.verdict, "views": self.brick.views,
                                "pick_attempts": self.brick.pick_attempts, "regrasps": self.brick.regrasps})
        self.brick = Brick(self.brick.idx + 1)
        self._move(S.HOME, "home", q, now)

    # ---- main tick -----------------------------------------------------------------------------
    def update(self, q, frames: dict, now: float):
        q = np.asarray(q, np.float32)
        if self.ctrl is None and self.state == S.HOME:     # first tick
            self._move(S.HOME, "home", q, now)
        self._transition(q, frames, now)
        action = self.ctrl.step(q, frames, now) if self.ctrl is not None else q
        self.last_cmd = np.asarray(action, np.float32)
        return self.last_cmd

    def _transition(self, q, frames, now):
        st = self.state
        if st in (S.DONE, S.FAULT):
            return
        done = self.ctrl.done(q, frames, now) if hasattr(self.ctrl, "done") else False

        # timeouts on every moving state
        if not done and self._timed_out(now) and st not in (S.INSPECT,):
            self.counters["timeouts"] += 1
            self._ev("timeout", {"after_s": round(now - self.t_state, 2)})
            if st == S.PICK_PRESENT:
                self.brick.pick_attempts += 1
                insp = np.asarray(self.cfg["poses"]["inspect"], np.float32)
                if np.max(np.abs(np.asarray(q, np.float32)[:4] - insp[:4])) < self.pick_near_inspect:
                    # near the camera without "arriving": snap there and let CHECK_HELD decide
                    self._move(S.SNAP_TO_INSPECT, "inspect", q, now)
                elif self.brick.pick_attempts < self.max_pick_attempts:
                    # still busy at the plate: let the policy keep trying from where it is (no trip home)
                    self._ev("pick_continue", {"attempt": self.brick.pick_attempts})
                    self._skill(S.PICK_PRESENT, "pick_present", q, now)
                else:
                    # out of tries: show the camera what it has; CHECK_HELD decides (as before)
                    self._move(S.SNAP_TO_INSPECT, "inspect", q, now)
            elif st in (S.PLACE_GOOD, S.PLACE_DEFECT):
                # brick may still be in the gripper: go to confirm, it decides
                self._release(q, now, after="place_timeout")
            elif st == S.HOME and self.brick.idx == 0 and not self.results:
                self.fault("cannot_reach_home", q, now)
            else:
                self.fault(f"timeout_{st.value.lower()}", q, now)
            return

        if st == S.HOME and done:
            if len(self.results) >= self.max_bricks:
                self._ev("max_bricks_reached")
                self._hold(S.DONE, q, now)
                return
            empty = self.checks.plate_empty(frames)
            if empty:
                self._ev("plate_empty")
                self._hold(S.DONE, q, now)
                return
            ready = getattr(self.checks, "next_brick_ready", None)
            if ready is not None and self.brick.pick_attempts == 0 and not ready(self.brick.idx):
                self.t_state = now        # waiting for the human is not a move timeout
                return                    # one-by-one mode: wait at home until a human has put the next brick in
            self._skill(S.PICK_PRESENT, "pick_present", q, now)

        elif st == S.PICK_PRESENT and done:
            self.brick.pick_attempts += 1
            self._move(S.SNAP_TO_INSPECT, "inspect", q, now)

        elif st == S.SNAP_TO_INSPECT and done:
            self._hold(S.CHECK_HELD, q, now, timeout=1.0)

        elif st == S.CHECK_HELD:
            held = self.checks.brick_held(frames)
            if held:
                self._start_inspect(q, frames, now)
            else:
                self.counters["no_brick"] += 1
                self._ev("no_brick", {"source": "check_held", "attempt": self.brick.pick_attempts})
                self._retry_pick_or_skip(q, now, reason="no_brick")

        elif st == S.INSPECT:
            res = self.inspector.poll()
            if res is None:
                if self._timed_out(now):
                    self.counters["timeouts"] += 1
                    self._ev("timeout", {"what": "inspector"})
                    self.brick.views.append({"view": self._view_name(), "score": None})
                    self._hold(S.DECIDE, q, now)
                return
            r = res if isinstance(res, dict) else getattr(res, "__dict__", {})
            if r.get("verdict") == NO_BRICK:
                self.counters["no_brick"] += 1
                self._ev("no_brick", {"source": "inspector"})
                self._retry_pick_or_skip(q, now, reason="no_brick")
                return
            self.brick.views.append({"view": self._view_name(), "score": float(r["score"])})
            self._ev("inspection", {k: r.get(k) for k in ("score", "verdict", "latency_ms", "device", "heatmap_png")})
            self._hold(S.DECIDE, q, now)

        elif st == S.DECIDE:
            scores = [v["score"] for v in self.brick.views if v["score"] is not None]
            verdict, score = decide(scores, self.t_low, self.t_high) if scores else (UNCERTAIN, None)
            self._ev("verdict", {"verdict": verdict, "score": score, "views": self.brick.views,
                                 "t_low": self.t_low, "t_high": self.t_high})
            if verdict == UNCERTAIN:
                self.counters["uncertain"] += 1
                if len(self.brick.views) < self.max_views:
                    self._move(S.NEXT_VIEW, VIEW_POSES[len(self.brick.views)], q, now)
                    return
                if self.brick.regrasps < self.max_regrasps:
                    self.brick.regrasps += 1
                    self.counters["regrasps"] += 1
                    self._move(S.REGRASP, "above_plate", q, now)
                    return
                verdict = DEFECT
                self._ev("uncertain_to_defect", {"score": score})
            self.brick.verdict = verdict
            self.before_place = self.checks.snapshot(frames)
            self._skill(S.PLACE_GOOD if verdict == GOOD else S.PLACE_DEFECT,
                        "place_good" if verdict == GOOD else "place_defect", q, now)

        elif st == S.NEXT_VIEW and done:
            self._start_inspect(q, frames, now)

        elif st == S.REGRASP and done:
            # above_plate pose has the gripper open: the brick drops back on the plate; pick again
            self.brick.views = []
            if self.on_put_back:
                self.on_put_back()
            self._ev("put_back")
            self._move(S.HOME, "home", q, now)

        elif st == S.CONFIRM:
            if now - self.t_state < self.release_s:
                return                    # gripper opening fully over the bowl before any move home
            ok = self.checks.placed_ok(self.before_place, frames)
            if ok is None and not self._timed_out(now):
                return
            if not ok:
                self.counters["unconfirmed"] += 1
                self._ev("place_unconfirmed")
            else:
                self._ev("place_confirmed")
            self._next_brick(q, now, self.brick.verdict)

        elif st in (S.PLACE_GOOD, S.PLACE_DEFECT) and done:
            self._release(q, now)

    def _release(self, q, now, **data):
        """Stay where the place skill ended and open the gripper wide, so the brick is surely out before going
        home (the home route keeps the gripper open until the last, downward step)."""
        cmd = (self.last_cmd if self.last_cmd is not None else np.asarray(q, np.float32)).copy()
        cmd[5] = max(float(cmd[5]), float(q[5]), self.release_open)
        self._enter(S.CONFIRM, q, now, Hold(cmd), self.release_s + 2.0, release_open=round(float(cmd[5]), 1), **data)

    def _view_name(self):
        return VIEW_POSES[min(len(self.brick.views), len(VIEW_POSES) - 1)]

    def _start_inspect(self, q, frames, now):
        cam = self.cfg["inspection"]["camera"]
        view = self._view_name()
        self._hold(S.INSPECT, q, now, timeout=self.inspect_timeout, view=view)
        self.inspector.submit(frames.get(cam), view=view)

    def _retry_pick_or_skip(self, q, now, reason):
        if self.brick.pick_attempts < self.max_pick_attempts:
            self._ev("repick", {"reason": reason, "attempt": self.brick.pick_attempts})
            self._move(S.HOME, "home", q, now)
        else:
            self._ev("skip_brick", {"reason": reason})
            self._next_brick(q, now, "SKIPPED")
