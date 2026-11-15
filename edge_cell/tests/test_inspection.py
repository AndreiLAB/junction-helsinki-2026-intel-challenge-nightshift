"""REPLAY test of inspection/service.py on frames cut from duplo_v1 (skipped if data/model missing)."""
import glob
import time
import unittest
from pathlib import Path

import numpy as np

from common.config import ROOT

DATA = ROOT / "data/inspect_frames/v1"
MODEL = ROOT / "models/anomaly/current"


@unittest.skipUnless(DATA.exists() and MODEL.exists(), "no replay data or model")
class TestInspector(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from inspection.service import Inspector
        cls.ins = Inspector(heatmap_dir=ROOT / "runs/test_heatmaps")

    def _run(self, f):
        from PIL import Image
        self.ins.submit(np.asarray(Image.open(f).convert("RGB")), view="inspect")
        t = time.time()
        while (r := self.ins.poll()) is None:
            self.assertLess(time.time() - t, 10)
            time.sleep(0.01)
        return r

    def test_contract_fields(self):
        r = self._run(sorted(glob.glob(str(DATA / "test_good/*.png")))[0])
        for k in ("brick_idx", "ts", "verdict", "score", "t_low", "t_high", "views", "heatmap_png", "model",
                  "precision", "device", "latency_ms", "evidence"):
            self.assertIn(k, r)
        self.assertTrue(Path(r["heatmap_png"]).exists())

    def test_defects_not_called_good(self):
        fs = sorted(glob.glob(str(DATA / "defect/*.png")))[::4]
        verdicts = [self._run(f)["verdict"] for f in fs]
        self.assertEqual(verdicts.count("GOOD"), 0, verdicts)

    def test_none_frame_is_no_brick(self):
        self.ins.submit(None)
        time.sleep(0.2)
        self.assertEqual(self.ins.poll()["verdict"], "NO_BRICK")
