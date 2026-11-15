"""Real robot runner. Started ONLY by a human in the Robot tab:
  ./robot_test.sh poses                 slow tour of the taught poses; inspects at each view; saves reference pictures
  ./robot_test.sh skill pick_present    run one learned skill (also place_good / place_defect)
  ./start_demo.sh [N]                   full loop for N bricks
Every mode waits for GO, starts slowly, and stops cleanly on Ctrl+C (the arm holds its position).
Studio must not be on a recording / run screen (it would hold the arm)."""
from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from pathlib import Path

import numpy as np

from cell.motion import Route, plan_route
from cell.safety import Safety, SafetyStop
from common.config import ROOT, load_station, repo_path
from common.events import EventLog, new_run_id

POLICY_STATES = {"PICK_PRESENT", "PLACE_GOOD", "PLACE_DEFECT"}
REF_DIR = ROOT / "configs/reference"


def say(msg):
    print(msg, flush=True)


class RealChecks:
    """Simple CPU checks. brick_held: inspect picture differs from the empty-gripper reference."""

    def __init__(self, cfg, thr=12.0):
        from PIL import Image
        self.thr = thr
        p = REF_DIR / "inspect_inspect.png"
        self.ref = np.asarray(Image.open(p).convert("RGB"), np.float32) if p.exists() else None
        self.last_diff = None

    def brick_held(self, frames):
        if self.ref is None or frames.get("inspect") is None:
            return True
        f = frames["inspect"].astype(np.float32)
        h, w = f.shape[:2]
        sl = (slice(h // 6, h * 5 // 6), slice(w // 6, w * 5 // 6))
        self.last_diff = float(np.mean(np.abs(f[sl] - self.ref[sl])))
        return self.last_diff > self.thr

    def plate_empty(self, frames):
        return False                      # the run stops after N bricks (--bricks)

    one_by_one = False

    def next_brick_ready(self, idx):
        """One-by-one mode: at home before each new brick, ask the human to put it in and press Enter."""
        if not self.one_by_one:
            return True
        if getattr(self, "_asked", None) != idx:
            self._asked = idx
            if not hasattr(self, "_lines"):
                self._lines = __import__("queue").Queue()
                __import__("threading").Thread(target=lambda: [self._lines.put(l) for l in sys.stdin],
                                               daemon=True).start()
            while not self._lines.empty():
                self._lines.get_nowait()          # ignore old key presses
            say(f"\n>>> Brick {idx + 1}: put ONE brick in the blue bowl, take your hand away, press Enter.")
        try:
            self._lines.get_nowait()
            say("    starting")
            return True
        except Exception:
            return False

    def snapshot(self, frames):
        return None

    def placed_ok(self, before, frames):
        return True                       # place skill is 'done' only after the gripper opened (action_source)


class Rig:
    def __init__(self, cfg, speed, policy_speed, log):
        from cell.hw import Cameras, open_follower, read_q
        self.cfg, self.log, self.read_q = cfg, log, read_q
        self.table = np.asarray(cfg["safety"]["max_step_per_tick"], np.float32)
        self.speed, self.policy_speed = speed, policy_speed
        self.safety = Safety(cfg, clock=time.monotonic)
        self.fps = cfg["robot"]["fps"]
        say("Opening cameras...")
        self.cams = Cameras(cfg)
        self.cams.connect()
        say("Opening follower arm (it switches on and holds its position)...")
        self.robot = open_follower(cfg)
        self.q = read_q(self.robot)
        self.safety.reset(self.q)

    def frames(self):
        fr = self.cams.read()
        for n, t in self.cams.ts.items():
            self.safety.note_frame(n, t)
        return fr

    def send(self, action, policy=False):
        self.safety.max_step = self.table * (self.policy_speed if policy else self.speed)
        a = self.safety.filter(action, self.q)
        self.robot.send_action(a)
        return a

    def tick(self, fn, policy=False):
        """One control tick: read, fn(q, frames) -> action, check, send. Returns frames."""
        t0 = time.monotonic()
        self.q = self.read_q(self.robot)
        fr = self.frames()
        self.safety.check_frames(list(fr))
        a = fn(self.q, fr)
        self.send(a, policy)
        time.sleep(max(0.0, 1.0 / self.fps - (time.monotonic() - t0)))
        return fr

    def move_to(self, pose_name, keep_gripper=False, timeout=15.0):
        sa = self.cfg["safety"]
        targets = plan_route(self.q, self.cfg["poses"][pose_name], self.cfg["poses"].get("travel"))
        if keep_gripper:
            targets = [np.concatenate([t[:5], [self.q[5]]]).astype(np.float32) for t in targets]
        mv = Route(targets, self.table * self.speed, sa["settle_tol"], sa["settle_s"], keep_gripper=keep_gripper)
        mv.start(self.q, time.monotonic())
        t0 = time.monotonic()
        fr = None
        while not mv.done(self.q, fr, time.monotonic()):
            if time.monotonic() - t0 > timeout:
                self.log.log(-1, "MOVE", "timeout", {"pose": pose_name, "q": self.q})
                say(f"  ! could not settle at {pose_name} within {timeout}s (continuing)")
                break
            fr = self.tick(lambda q, f: mv.step(q, f, time.monotonic()))
        return self.frames()

    def close(self):
        try:
            self.robot.disconnect()       # follower keeps torque on: holds position
        except Exception as e:
            say(f"disconnect: {e}")
        self.cams.disconnect()


def wait_go(what):
    say("\n" + "=" * 70 + f"\n{what}\nClear the area around the arm. Keep a hand near its power switch.\n"
        "Ctrl+C stops at any time (the arm then holds still).\n" + "=" * 70)
    return input("Type GO and press Enter to start: ").strip().upper() == "GO"


def save_png(arr, path):
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr).save(path)


def mode_poses(rig, cfg, log, run_dir):
    from inspection.service import Inspector
    ins = Inspector(cfg, heatmap_dir=run_dir / "heatmaps")
    say(f"Inspector: {ins.model_name} on {ins.device}")
    tour = ["home", "inspect", "inspect_view2", "inspect_view3", "inspect", "above_plate", "home"]
    for name in tour:
        say(f"-> moving to {name}")
        fr = rig.move_to(name, keep_gripper=name.startswith("inspect"))
        log.log(-1, "POSES", "reached", {"pose": name, "q": rig.q})
        for cam, img in fr.items():
            save_png(img, run_dir / f"{name}_{cam}.png")
        if name.startswith("inspect"):
            s, _, ms = ins.score(fr["inspect"])
            say(f"   inspect score {s:.2f} ({ins.verdict(s)}) in {ms:.0f} ms on {ins.device}")
            log.log(-1, "POSES", "inspection", {"pose": name, "score": s, "latency_ms": ms, "device": ins.device})
        if name in ("home", "inspect", "inspect_view2", "inspect_view3"):
            REF_DIR.mkdir(parents=True, exist_ok=True)
            for cam, img in fr.items():
                save_png(img, REF_DIR / f"{name}_{cam}.png")
    say(f"Tour done. Pictures in {run_dir}. Reference pictures in {REF_DIR}.")


def set_gripper(rig, value, secs=1.2):
    """Open/close only the gripper, holding the other joints."""
    hold = rig.q.copy()
    t0 = time.monotonic()
    while time.monotonic() - t0 < secs:
        a = hold.copy(); a[5] = value
        rig.tick(lambda q, f: a)


def mode_photos(rig, cfg, log, run_dir):
    """Photo session: a human puts a brick in the gripper; the arm shows it at all three views."""
    from inspection.service import Inspector
    ins = Inspector(cfg)
    out = ROOT / "data/inspect_frames/multiview" / run_dir.name
    say(f"Inspector: {ins.model_name} on {ins.device}. Photos go to {out}")
    views = ["inspect", "inspect_view2", "inspect_view3"]
    lines = __import__("queue").Queue()
    __import__("threading").Thread(target=lambda: [lines.put(l) for l in sys.stdin], daemon=True).start()

    def ask(prompt):
        say(prompt)
        while True:                      # keep the servo loop alive while waiting for the human
            try:
                return lines.get_nowait().strip().lower()
            except Exception:
                rig.tick(lambda q, f: rig.safety.last)

    i = 0
    rig.move_to("inspect")
    while True:
        set_gripper(rig, 45)
        lab = ask(f"\n[brick {i}] Put a brick between the open fingers and hold it there.\n"
                  "   Type g (good) or d (defective) and Enter (q = finish):")
        if lab.startswith("q"):
            break
        if lab[:1] not in ("g", "d"):
            say("   please type g, d or q")
            continue
        label = "good" if lab.startswith("g") else "defect"
        say("   closing gripper; let go of the brick")
        set_gripper(rig, 3, secs=1.5)
        scores = []
        for v in views:
            fr = rig.move_to(v, keep_gripper=True)
            set_gripper(rig, 3, secs=0.4)    # settle and refresh frames
            fr = rig.frames()
            save_png(fr["inspect"], out / label / f"b{i:03d}_{v}.png")
            s, _, ms = ins.score(fr["inspect"])
            scores.append(round(s, 2))
            log.log(i, "PHOTOS", "photo", {"label": label, "view": v, "score": s, "latency_ms": ms})
        say(f"   {label}: scores per view {scores} -> max {max(scores):.2f} ({ins.verdict(max(scores))})")
        rig.move_to("inspect", keep_gripper=True)
        ask("   Hold the brick, press Enter, then the gripper opens:")
        i += 1
    say(f"Photo session done: {i} bricks.")


def load_models(cfg, log):
    from cell.action_source import load_policy
    root = repo_path(cfg["models"]["policy_dir"])
    dev = cfg["models"]["policy_device"]
    per_skill = {s: root / s for s in ("pick_present", "place_good", "place_defect")}
    if all((p / "manifest.json").exists() for p in per_skill.values()):      # ladder (2): one ACT per skill
        out = {}
        for s, p in per_skill.items():
            out[s], used, t = load_policy(p, dev)
        mode = "act_per_skill"
    else:                                                                      # ladder (1): one model, text task
        m, used, t = load_policy(root, dev)
        out = {s: m for s in per_skill}
        mode = "single_model"
    pick_dir = cfg["models"].get("pick_policy_dir")
    if pick_dir:                                                               # a separate model only for picking
        pd = repo_path(pick_dir)
        out["pick_present"], used_p, tp = load_policy(pd, dev)
        mode += f"+pick:{pd.resolve().name}"
        log.log(-1, "INIT", "pick_policy_loaded", {"dir": str(pd.resolve()), "device": used_p, "load_s": round(tp, 2)})
        say(f"Pick model {pick_dir} on {used_p}, loaded in {tp:.1f}s")
    log.log(-1, "INIT", "policy_loaded", {"dir": str(root.resolve()), "device": used, "load_s": round(t, 2),
                                          "mode": mode})
    say(f"Policy {root.resolve().name} ({mode}) on {used}, loaded in {t:.1f}s")
    return out


def run_skill(rig, cfg, log, sk, skill_name):
    timeout = cfg["skills"][skill_name]["timeout_s"]
    say(f"-> running learned skill '{skill_name}': \"{sk.instruction}\" (timeout {timeout}s)")
    sk.start(rig.q, time.monotonic())
    t0 = time.monotonic()
    result = "timeout"
    target = np.asarray(cfg["poses"]["inspect"], np.float32)
    next_log = t0
    while time.monotonic() - t0 < timeout:
        fr = rig.tick(lambda q, f: sk.step(q, f, time.monotonic()), policy=True)
        if time.monotonic() >= next_log:
            next_log += 1.0
            log.log(-1, "SKILL", "q", {"skill": skill_name, "t": round(time.monotonic() - t0, 1), "q": rig.q,
                                       "dist_inspect": float(np.max(np.abs(rig.q[:4] - target[:4]))),
                                       "still": sk.still()})
        if sk.done(rig.q, fr, time.monotonic()):
            result = "done"
            break
    lat = np.asarray(sk.latencies or [np.nan])
    data = {"skill": skill_name, "result": result, "s": round(time.monotonic() - t0, 1), "chunks": len(sk.latencies),
            "infer_ms_p50": float(np.nanmedian(lat)), "infer_ms_p95": float(np.nanpercentile(lat, 95)),
            "rate_limited_ticks": rig.safety.n_rate_limited, "clamped_ticks": rig.safety.n_clamped}
    log.log(-1, "SKILL", "skill_end", data)
    say(f"Skill ended: {result} after {data['s']}s; policy inference p50 {data['infer_ms_p50']:.0f} ms")
    return result


def mode_skill(rig, cfg, log, skill_arg, run_dir, handed=False):
    """skill_arg: one skill, or a chain like pick_present,place_good. A place skill needs a brick: the arm picks
    one first, or with handed=True a human puts one in the gripper at the inspection point."""
    from cell.action_source import make_policy_skills
    chain = [s.strip() for s in skill_arg.split(",") if s.strip()]
    if chain[0] != "pick_present" and not handed:
        chain = ["pick_present"] + chain
        say("(a place skill needs a brick in the gripper, so the arm picks one first)")
    skills = make_policy_skills(load_models(cfg, log), cfg, log)
    for sk in skills.values():
        sk.record_dir = run_dir / "policy_inputs"
    if chain[0] != "pick_present":
        say("-> moving to the inspection point")
        rig.move_to("inspect")
        set_gripper(rig, 45)
        lines = __import__("queue").Queue()
        __import__("threading").Thread(target=lambda: [lines.put(l) for l in sys.stdin], daemon=True).start()
        say("\nPut a brick between the open fingers, hold it there, and press Enter.")
        while True:                      # keep the servo loop alive while waiting
            try:
                lines.get_nowait()
                break
            except Exception:
                rig.tick(lambda q, f: rig.safety.last)
        say("   closing gripper; let go of the brick")
        set_gripper(rig, 3, secs=1.5)
        log.log(-1, "SKILL", "brick_handed", {"q": rig.q})
    else:
        say("-> moving to home first")
        rig.move_to("home")
    for name in chain:
        result = run_skill(rig, cfg, log, skills[name], name)
        if name == "pick_present":
            fr = rig.move_to("inspect", keep_gripper=True)
            save_png(fr["inspect"], run_dir / "held_inspect.png")
            say("At the inspection point. Picture saved.")
        elif result == "done":
            say("-> brick released; going back home (saved move)")
            rig.move_to("home")
    say("Now holding still. Press Ctrl+C to finish.")
    while True:
        rig.tick(lambda q, f: rig.safety.last)


def mode_run(rig, cfg, log, n_bricks, run_dir, scripted_place=False, one_by_one=False):
    from cell.action_source import make_policy_skills
    from cell.statemachine import CellStateMachine
    from inspection.service import Inspector
    ins = Inspector(cfg, heatmap_dir=run_dir / "heatmaps")
    say(f"Inspector: {ins.model_name} on {ins.device}")
    skills = make_policy_skills(load_models(cfg, log), cfg, log, scripted_place=scripted_place)
    for sk in skills.values():
        if hasattr(sk, "record_dir"):
            sk.record_dir = run_dir / "policy_inputs"
    log.log(-1, "INIT", "skills", {"place": "scripted (ladder 3)" if scripted_place else "learned"})
    say("Placing: " + ("SAVED MOVES (fallback)" if scripted_place else "learned policy"))
    checks = RealChecks(cfg)
    checks.one_by_one = one_by_one
    sm = CellStateMachine(cfg, skills, ins, checks, log, max_bricks=n_bricks)
    t0 = time.monotonic()
    last_state = None
    while not sm.finished:
        ins.brick_idx = sm.brick.idx
        rig.tick(lambda q, f: sm.update(q, f, time.monotonic()), policy=sm.state.value in POLICY_STATES)
        if sm.state != last_state:
            say(f"[{time.monotonic() - t0:6.1f}s] brick {sm.brick.idx}: {sm.state.value}")
            last_state = sm.state
    from cell.run import summarize
    s = summarize(sm)
    s["wall_s"] = round(time.monotonic() - t0, 1)
    s["s_per_brick"] = round(s["wall_s"] / max(1, s["bricks"]), 1)
    log.log(-1, sm.state.value, "run_end", s)
    say("RUN END: " + json.dumps(s))
    say("Holding still. Press Ctrl+C to finish.")
    while True:
        rig.tick(lambda q, f: rig.safety.last)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["poses", "skill", "run", "photos"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--speed", type=float, default=None, help="scripted-move speed 0..1 (default from config)")
    ap.add_argument("--scripted-place", action="store_true", help="ladder (3): taught moves for placing")
    ap.add_argument("--policy-speed", type=float, default=None, help="learned-skill speed multiplier (default from config)")
    ap.add_argument("--pick-model", default=None,
                    help="separate model for picking, a folder in models/policy (e.g. act_v2); placing uses current")
    ap.add_argument("--one-by-one", action="store_true",
                    help="run: before each brick, wait at home until a human has put one brick in and pressed Enter")
    ap.add_argument("--handed", action="store_true",
                    help="place test: a human puts the brick in the gripper at the inspection point (no pick)")
    ap.add_argument("--horizon", type=int, default=None,
                    help="use only the first N predicted actions, then re-plan from a fresh picture")
    a = ap.parse_args(argv)
    cfg = copy.deepcopy(load_station())
    speed = a.speed if a.speed is not None else cfg["safety"]["speed"]
    if a.policy_speed is None:
        a.policy_speed = float(cfg["safety"].get("policy_speed", 1.0))
    if a.horizon:
        cfg["run"]["exec_horizon"] = a.horizon
    if a.pick_model:
        cfg["models"]["pick_policy_dir"] = f"models/policy/{a.pick_model}"
    run_id = new_run_id(a.mode + (f"-{a.arg}" if a.arg else ""))
    what = {"poses": "SLOW TOUR of the saved positions (no brick in the gripper, please).",
            "skill": f"LEARNED SKILL test: {a.arg}",
            "photos": "PHOTO SESSION: the arm waits at the inspection point; you hand it bricks.",
            "run": f"FULL SORTING RUN for {a.arg or cfg['run']['max_bricks']} bricks"}[a.mode]
    if not wait_go(what):
        say("Not started.")
        return 0
    log = EventLog(run_id, echo=False)
    run_dir = log.dir
    log.log(-1, "INIT", "run_start", {"mode": a.mode, "arg": a.arg, "speed": speed, "policy_speed": a.policy_speed,
                                      "exec_horizon": cfg["run"].get("exec_horizon"),
                                      "evidence": "REAL"})
    rig = None
    try:
        rig = Rig(cfg, speed, a.policy_speed, log)
        log.log(-1, "INIT", "start_pose", {"q": [round(float(x), 1) for x in rig.q]})
        if a.mode == "poses":
            mode_poses(rig, cfg, log, run_dir)
        elif a.mode == "photos":
            mode_photos(rig, cfg, log, run_dir)
        elif a.mode == "skill":
            mode_skill(rig, cfg, log, a.arg or "pick_present", run_dir, a.handed)
        else:
            mode_run(rig, cfg, log, int(a.arg or cfg["run"]["max_bricks"]), run_dir, a.scripted_place, a.one_by_one)
    except KeyboardInterrupt:
        say("\nStopped by Ctrl+C.")
        log.log(-1, "STOP", "ctrl_c")
    except SafetyStop as e:
        say(f"\nSAFETY STOP: {e}")
        log.log(-1, "FAULT", "safety_stop", {"reason": str(e)})
    except Exception as e:
        say(f"\nERROR: {e!r}")
        log.log(-1, "FAULT", "error", {"error": repr(e)})
        raise
    finally:
        if rig is not None:
            rig.close()
        log.close()
        say(f"Log: {run_dir / 'events.jsonl'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
