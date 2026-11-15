"""Run the cell.

  python -m cell.run --mock            fake robot, fake inspector, 5 bricks; writes runs/<id>/events.jsonl
  python -m cell.run --mock --bricks good,defect,unsure,good,defect --miss 1

Real mode (robot) is started only by a human from the Robot tab via ./robot_test.sh or ./start_demo.sh.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import time

import numpy as np

from cell.fakes import FakeChecks, FakeInspector, FakeRobot, FakeWorld, make_fake_skills
from cell.statemachine import CellStateMachine
from common.config import load_station
from common.events import EventLog, new_run_id


def summarize(sm: CellStateMachine, world=None) -> dict:
    finals = [b.final for b in sm.results]
    out = {"bricks": len(finals), "good": finals.count("GOOD"), "defect": finals.count("DEFECT"),
           "skipped": finals.count("SKIPPED"), "state": sm.state.value, "fault": sm.fault_reason,
           **sm.counters}
    if world is not None:
        out["truth_good_bowl"] = world.bowls["good"]
        out["truth_defect_bowl"] = world.bowls["defect"]
    return out


def run_mock(bricks, miss=(), max_s=120.0, echo=True, cfg=None):
    cfg = copy.deepcopy(cfg or load_station())
    cfg["safety"]["speed"] = 1.0
    cfg["safety"]["settle_s"] = 0.05
    world = FakeWorld(bricks, miss_first_pick=miss)
    max_step = np.asarray(cfg["safety"]["max_step_per_tick"], np.float32) * 3
    skills = make_fake_skills(world, cfg["poses"], max_step)
    log = EventLog(new_run_id("mock"), echo=echo)
    log.log(-1, "INIT", "run_start", {"mode": "MOCK", "bricks": bricks})
    sm = CellStateMachine(cfg, skills, FakeInspector(world, t_low=cfg["inspection"]["t_low"],
                                                     t_high=cfg["inspection"]["t_high"]),
                          FakeChecks(world), log, max_bricks=len(bricks) + 5,
                          on_put_back=lambda: world.drop("plate"))
    robot = FakeRobot(np.zeros(6, np.float32))
    frames = {"top": np.zeros((480, 640, 3), np.uint8), "inspect": np.zeros((480, 640, 3), np.uint8),
              "wrist": np.zeros((480, 640, 3), np.uint8)}
    t0 = time.monotonic()
    while not sm.finished and time.monotonic() - t0 < max_s:
        q = robot.step()
        robot.send(sm.update(q, frames, time.monotonic()))
        time.sleep(0.001)
    summary = summarize(sm, world)
    summary["wall_s"] = round(time.monotonic() - t0, 2)
    log.log(-1, sm.state.value, "run_end", summary)
    log.close()
    return sm, world, summary, log


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--bricks", default="good,defect,unsure,good,defect")
    ap.add_argument("--miss", default="", help="plate positions whose first pick misses, e.g. 1,3")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    if not a.mock:
        print("Real mode is started from the Robot tab with ./robot_test.sh or ./start_demo.sh")
        return 2
    miss = [int(x) for x in a.miss.split(",") if x]
    sm, world, summary, log = run_mock(a.bricks.split(","), miss, echo=not a.quiet)
    print(json.dumps(summary))
    print(f"events: {log.path}")
    ok = sm.state.value == "DONE"
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
