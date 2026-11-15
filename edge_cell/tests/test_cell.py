"""Run: <backend python> -m unittest discover -s tests -t . -v"""
import copy
import unittest

import numpy as np

from cell.run import run_mock
from cell.safety import Safety, SafetyStop
from cell.statemachine import DEFECT, GOOD, UNCERTAIN, decide
from common.config import load_station

CFG = load_station()


class TestVerdictRule(unittest.TestCase):
    def test_rule(self):
        self.assertEqual(decide([0.1], 0.4, 0.6), (GOOD, 0.1))
        self.assertEqual(decide([0.9], 0.4, 0.6), (DEFECT, 0.9))
        self.assertEqual(decide([0.5], 0.4, 0.6)[0], UNCERTAIN)
        self.assertEqual(decide([0.1, 0.7], 0.4, 0.6), (DEFECT, 0.7))   # max over views
        self.assertEqual(decide([0.4], 0.4, 0.6)[0], UNCERTAIN)          # boundaries are uncertain
        self.assertEqual(decide([0.6], 0.4, 0.6)[0], UNCERTAIN)


class TestMockRun(unittest.TestCase):
    def test_five_bricks(self):
        sm, world, s, log = run_mock(["good", "defect", "unsure", "good", "defect"], miss=[1], echo=False)
        self.assertEqual(s["state"], "DONE")
        self.assertEqual(world.bowls["good"], ["good", "good"])
        self.assertEqual(sorted(world.bowls["defect"]), ["defect", "defect", "unsure"])
        self.assertEqual(s["regrasps"], 1)
        self.assertGreaterEqual(s["no_brick"], 1)
        self.assertTrue(log.path.exists())
        ev = [e["event"] for e in log.events]
        for needed in ("verdict", "repick", "put_back", "uncertain_to_defect", "brick_done", "run_end"):
            self.assertIn(needed, ev)

    def test_always_missing_brick_is_skipped(self):
        sm, world, s, log = run_mock(["good"], miss=[0], echo=False)
        self.assertEqual(s["state"], "DONE")
        self.assertEqual(world.bowls["good"], ["good"])  # second try succeeds

    def test_event_fields(self):
        sm, world, s, log = run_mock(["good"], echo=False)
        for e in log.events:
            self.assertEqual(set(e), {"ts", "run_id", "brick_idx", "state", "event", "data"})


class TestSafety(unittest.TestCase):
    def setUp(self):
        self.t = [0.0]
        cfg = copy.deepcopy(CFG)
        cfg["safety"]["speed"] = 1.0
        self.s = Safety(cfg, clock=lambda: self.t[0])

    def test_clamp(self):
        start = self.s.hi.copy(); start[0] -= 0.5
        self.s.reset(start)
        a = self.s.filter(np.array([500, *start[1:]]))
        self.assertLessEqual(a[0], self.s.hi[0])
        self.assertEqual(self.s.n_clamped, 1)

    def test_rate_limit(self):
        self.s.reset(np.zeros(6))
        a = self.s.filter(np.full(6, 50.0))
        np.testing.assert_allclose(a, np.minimum(50, self.s.max_step))
        self.assertEqual(self.s.n_rate_limited, 1)

    def test_gripper_lower_bound(self):
        self.s.reset(np.zeros(6))
        self.assertGreaterEqual(self.s.filter(np.array([0, 0, 0, 0, 0, -30.0]))[5], 0)

    def test_bad_action(self):
        with self.assertRaises(SafetyStop):
            self.s.filter(np.array([np.nan] * 6))
        with self.assertRaises(SafetyStop):
            self.s.filter(np.zeros(5))

    def test_stale_frames(self):
        self.s.note_frame("inspect")
        self.s.check_frames(["inspect"])
        self.t[0] = 1.0
        with self.assertRaises(SafetyStop):
            self.s.check_frames(["inspect"])
        with self.assertRaises(SafetyStop):
            self.s.check_frames(["top"])        # never seen


if __name__ == "__main__":
    unittest.main()


class TestRoute(unittest.TestCase):
    def test_up_sideways_down(self):
        from cell.motion import plan_route
        travel = [0, -60, 60, 30, 0, 10]
        r = plan_route([80, 50, -60, 80, 20, 3], [-70, 0, 0, 85, 0, 16], travel)
        self.assertEqual(len(r), 3)
        self.assertEqual(r[0][0], 80)          # raise first, same pan
        self.assertEqual(list(r[0][1:4]), [-60, 60, 30])
        self.assertEqual(r[1][0], -70)         # turn while raised
        self.assertEqual(list(r[1][1:4]), [-60, 60, 30])
        self.assertEqual(r[2][0], -70)         # then down
        self.assertEqual(len(plan_route([0] * 6, [5, 0, 0, 0, 0, 0], travel)), 1)   # small move: direct
        self.assertEqual(len(plan_route([80] + [0] * 5, [-70] + [0] * 5, None)), 1)  # no travel pose: direct
        # same pan but starting low (e.g. stopped inside a bowl): still go up first
        self.assertEqual(len(plan_route([70, 0, 40, 50, 0, 3], [75, 59, -60, 81, 25, 2], travel)), 3)


class TestPickTimeout(unittest.TestCase):
    def _sm(self):
        import time
        from cell.fakes import FakeChecks, FakeInspector, FakeWorld, make_fake_skills
        from cell.motion import Hold
        from cell.statemachine import CellStateMachine, S
        from common.events import EventLog, new_run_id
        cfg = copy.deepcopy(CFG)
        cfg["skills"]["pick_present"]["timeout_s"] = 0.2
        world = FakeWorld(["good"])
        skills = make_fake_skills(world, cfg["poses"], np.ones(6, np.float32) * 5)

        class Stuck(Hold):                       # policy that never finishes
            instruction = "stuck"

            def start(self, q, now):
                pass

            def done(self, q, frames, now):
                return False
        skills["pick_present"] = Stuck(np.asarray(cfg["poses"]["above_plate"], np.float32))
        log = EventLog(new_run_id("mock-timeout"), echo=False)
        sm = CellStateMachine(cfg, skills, FakeInspector(world, 0.45, 0.6), FakeChecks(world), log, max_bricks=1)
        sm._skill(S.PICK_PRESENT, "pick_present", np.zeros(6, np.float32), time.monotonic())
        return sm, log, S, time

    def test_timeout_at_plate_keeps_trying_then_snaps(self):
        sm, log, S, time = self._sm()
        q = np.asarray(CFG["poses"]["above_plate"], np.float32)
        frames = {k: np.zeros((480, 640, 3), np.uint8) for k in ("top", "inspect", "wrist")}
        t = time.monotonic()
        states = []
        for i in range(CFG["run"]["max_pick_attempts"]):
            t += 0.5
            sm.update(q, frames, t)
            states.append(sm.state)
        self.assertEqual(states[:-1], [S.PICK_PRESENT] * (len(states) - 1))   # no trip home
        self.assertEqual(states[-1], S.SNAP_TO_INSPECT)
        self.assertNotIn("repick", [e["event"] for e in log.events])

    def test_timeout_near_camera_snaps(self):
        sm, log, S, time = self._sm()
        q = np.asarray(CFG["poses"]["inspect"], np.float32) + 10
        frames = {k: np.zeros((480, 640, 3), np.uint8) for k in ("top", "inspect", "wrist")}
        sm.update(q, frames, time.monotonic() + 0.5)
        self.assertEqual(sm.state, S.SNAP_TO_INSPECT)


class TestOneByOne(unittest.TestCase):
    def test_waits_for_human_each_brick(self):
        from cell.fakes import FakeChecks
        asked = []

        def ready(self_, idx):
            asked.append(idx)
            return asked.count(idx) > 3        # human presses Enter after a few ticks
        FakeChecks.next_brick_ready = ready
        try:
            sm, world, s, log = run_mock(["good", "defect"], echo=False)
        finally:
            del FakeChecks.next_brick_ready
        self.assertEqual(s["state"], "DONE")
        self.assertEqual(sorted(set(asked)), [0, 1])
