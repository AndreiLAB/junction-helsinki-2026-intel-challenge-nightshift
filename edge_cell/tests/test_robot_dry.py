"""Dry run of cell/robot.py with a fake arm, fake cameras and a fake policy (no hardware)."""
import time
import unittest
from unittest import mock

import numpy as np

import cell.hw as hw
import cell.robot as robot
from cell.fakes import FakeRobot
from common.config import load_station

CFG = load_station()


class FakeCams:
    def __init__(self, cfg, names=("top", "inspect", "wrist")):
        self.names, self.ts = names, {}
        self.n = 0

    def connect(self, timeout=10):
        pass

    def read(self):
        self.n += 1
        img = np.full((480, 640, 3), 40 + (self.n // 30) % 2 * 60, np.uint8)
        self.ts = {n: time.monotonic() for n in self.names}
        return {n: img for n in self.names}

    def disconnect(self):
        pass


class FakeArm(FakeRobot):
    def __init__(self):
        super().__init__(np.asarray(CFG["poses"]["home"], np.float32) + 3, alpha=0.6)

    def get_observation(self):
        self.step()
        return type("O", (), {"state": self.q.copy()})()

    def send_action(self, a, goal_time=0.1):
        self.send(a)

    def disconnect(self):
        pass


class FakeFeat:
    def __init__(self, n):
        self.name = n


class FakePolicy:
    """Pick: go to inspect pose. Place: go to above_plate pose and open the gripper."""
    input_features = [FakeFeat("state"), FakeFeat("images.top"), FakeFeat("images.inspect"),
                      FakeFeat("images.wrist"), FakeFeat("task")]

    def reset(self):
        pass

    def predict_action_chunk(self, o):
        time.sleep(0.05)
        q = o["state"][0]
        tgt = np.asarray(CFG["poses"]["inspect"] if "inspection" in o["task"][0] else CFG["poses"]["above_plate"],
                         np.float32).copy()
        if "inspection" not in o["task"][0]:
            tgt[5] = 60
        return np.linspace(q, tgt, 30).astype(np.float32)


class TestDry(unittest.TestCase):
    def patches(self, arm):
        import tempfile
        from pathlib import Path
        return [mock.patch.object(robot, "REF_DIR", Path(tempfile.mkdtemp())),
                mock.patch.object(hw, "open_follower", lambda cfg: arm),
                mock.patch.object(hw, "Cameras", FakeCams),
                mock.patch.object(robot, "load_models",
                                  lambda cfg, log: {s: FakePolicy() for s in ("pick_present", "place_good", "place_defect")}),
                mock.patch("builtins.input", lambda *a: "GO")]

    def run_mode(self, args, stop_after_s):
        arm = FakeArm()
        ps = self.patches(arm)
        for p in ps:
            p.start()
        t0 = time.monotonic()
        real_tick = robot.Rig.tick

        def tick(self_, fn, policy=False):
            if time.monotonic() - t0 > stop_after_s:
                raise KeyboardInterrupt
            return real_tick(self_, fn, policy)
        with mock.patch.object(robot.Rig, "tick", tick):
            try:
                rc = robot.main(args)
            finally:
                for p in ps:
                    p.stop()
        return rc, arm

    def test_poses_tour(self):
        rc, arm = self.run_mode(["poses", "--speed", "1.0"], 60)
        self.assertEqual(rc, 0)
        np.testing.assert_allclose(arm.q[:5], CFG["poses"]["home"][:5], atol=3)

    def test_skill_pick(self):
        rc, arm = self.run_mode(["skill", "pick_present"], 20)
        self.assertEqual(rc, 0)

    def test_full_run_two_bricks(self):
        rc, arm = self.run_mode(["run", "2", "--speed", "1.0"], 90)
        self.assertEqual(rc, 0)

    def test_skill_place_handed(self):
        import io
        with mock.patch("sys.stdin", io.StringIO("\n")):
            rc, arm = self.run_mode(["skill", "place_defect", "--handed", "--speed", "1.0"], 40)
        self.assertEqual(rc, 0)

    def test_skill_chain_place(self):
        import json
        from common.config import ROOT
        rc, arm = self.run_mode(["skill", "place_good", "--speed", "1.0"], 45)
        self.assertEqual(rc, 0)
        run = sorted((ROOT / "runs").glob("*skill-place_good*"), key=lambda p: p.stat().st_mtime)[-1]
        ends = [json.loads(l)["data"] for l in open(run / "events.jsonl") if '"skill_end"' in l]
        self.assertEqual([e["skill"] for e in ends], ["pick_present", "place_good"])
        self.assertEqual(ends[1]["result"], "done")


if __name__ == "__main__":
    unittest.main()


class TestPhotosDry(TestDry):
    test_poses_tour = test_skill_pick = test_full_run_two_bricks = test_skill_chain_place = test_skill_place_handed = None

    def test_photos(self):
        import io
        import shutil
        with mock.patch("sys.stdin", io.StringIO("g\n\nd\n\nq\n")):
            rc, arm = self.run_mode(["photos", "--speed", "1.0"], 120)
        self.assertEqual(rc, 0)
        from common.config import ROOT
        d = sorted((ROOT / "data/inspect_frames/multiview").glob("*photos"))[-1]
        self.assertEqual(len(list(d.rglob("*.png"))), 6)
        shutil.rmtree(d)   # fake pictures must not pollute the training data


class TestScriptedPlaceDry(TestDry):
    test_poses_tour = test_skill_pick = test_full_run_two_bricks = test_skill_chain_place = test_skill_place_handed = None

    def test_run_scripted_place(self):
        import copy as _copy
        cfg = _copy.deepcopy(CFG)
        cfg["poses"].setdefault("above_good", cfg["poses"]["above_plate"])
        cfg["poses"].setdefault("above_defect", cfg["poses"]["above_plate"])
        with mock.patch.object(robot, "load_station", lambda: cfg):
            rc, arm = self.run_mode(["run", "1", "--speed", "1.0", "--scripted-place"], 120)
        self.assertEqual(rc, 0)
        from common.config import ROOT
        d = sorted((ROOT / "runs").glob("*-run-1"))[-1]
        ev = (d / "events.jsonl").read_text()
        self.assertIn('"run_end"', ev)
        self.assertIn('"bricks": 1', ev)
