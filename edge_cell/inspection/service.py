"""Inspector used by the robot loop (contract: docs/CONTRACTS.md).
  submit(frame_rgb, depth_mm=None, view="inspect") -> None   returns at once (work runs in a thread)
  poll() -> dict | None                                       None while still working
Runs the Anomalib OpenVINO export with plain openvino (no anomalib needed in the robot venv).
Device from configs/station.yaml (NPU wanted; falls back to CPU if the device is not available)."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import numpy as np

from common.config import load_station, repo_path

GOOD, DEFECT, UNCERTAIN, NO_BRICK = "GOOD", "DEFECT", "UNCERTAIN", "NO_BRICK"


class Inspector:
    def __init__(self, cfg: dict | None = None, model_dir: str | Path | None = None, device: str | None = None,
                 heatmap_dir: str | Path | None = None):
        import openvino as ov

        cfg = cfg or load_station()
        ins = cfg["inspection"]
        self.t_low, self.t_high = float(ins["t_low"]), float(ins["t_high"])
        self.crop = ins.get("crop_enabled") and ins.get("crop")
        mdir = repo_path(model_dir or cfg["models"]["anomaly_dir"])
        xml = next(mdir.rglob("model.xml"))
        card = mdir / "MODEL_CARD.json"
        self.model_name = json.loads(card.read_text())["name"] if card.exists() else mdir.name
        core = ov.Core()
        want = device or cfg["models"]["anomaly_device"]
        self.device = want if want in core.available_devices else "CPU"
        m = core.read_model(str(xml))
        self.batch = m.inputs[0].partial_shape[0].get_length() if m.inputs[0].partial_shape[0].is_static else 1
        self.h, self.w = int(cfg["cameras"]["inspect"]["height"]), int(cfg["cameras"]["inspect"]["width"])
        m.reshape([self.batch, 3, self.h, self.w])
        t = time.perf_counter()
        self.cm = core.compile_model(m, self.device)
        self.compile_s = time.perf_counter() - t
        self.precision = str(m.inputs[0].element_type)
        self.heatmap_dir = Path(heatmap_dir) if heatmap_dir else None
        self._lock = threading.Lock()
        self._result = None
        self._busy = False
        self.brick_idx = None

    # ---- contract ----------------------------------------------------------------------------
    def submit(self, frame_rgb, depth_mm=None, view="inspect"):
        with self._lock:
            self._result, self._busy = None, True
        threading.Thread(target=self._work, args=(None if frame_rgb is None else np.array(frame_rgb), view),
                         daemon=True).start()

    def poll(self):
        with self._lock:
            r = self._result
            if r is not None:
                self._result = None
        return r

    # ---- work ----------------------------------------------------------------------------------
    def score(self, frame_rgb):
        """Return (score 0..1, anomaly_map HxW float, latency_ms)."""
        x = frame_rgb
        if x.shape[:2] != (self.h, self.w):
            from PIL import Image
            x = np.asarray(Image.fromarray(x).resize((self.w, self.h)))
        x = (x.astype(np.float32) / 255.0).transpose(2, 0, 1)[None]
        x = np.repeat(x, self.batch, axis=0)
        t = time.perf_counter()
        r = self.cm(x)
        ms = (time.perf_counter() - t) * 1000
        score = float(np.asarray(r["pred_score"]).ravel()[0])
        amap = np.asarray(r["anomaly_map"])[0, 0]
        return score, amap, ms

    def verdict(self, score):
        return GOOD if score < self.t_low else DEFECT if score > self.t_high else UNCERTAIN

    def _work(self, frame, view):
        try:
            if frame is None:
                res = {"verdict": NO_BRICK, "score": 0.0, "latency_ms": 0.0, "evidence": "no frame"}
            else:
                s, amap, ms = self.score(frame)
                res = {"verdict": self.verdict(s), "score": s, "latency_ms": round(ms, 1),
                       "heatmap_png": self._save_heatmap(frame, amap, view), "evidence": "REAL"}
        except Exception as e:  # never kill the loop: report as uncertain
            res = {"verdict": UNCERTAIN, "score": None, "latency_ms": None, "evidence": f"error: {e}"}
        res.update({"brick_idx": self.brick_idx, "ts": time.time(), "t_low": self.t_low, "t_high": self.t_high,
                    "views": [{"view": view, "score": res["score"]}], "model": self.model_name,
                    "precision": self.precision, "device": self.device})
        res.setdefault("heatmap_png", None)
        with self._lock:
            self._result, self._busy = res, False

    def _save_heatmap(self, frame, amap, view):
        if self.heatmap_dir is None:
            return None
        from PIL import Image
        self.heatmap_dir.mkdir(parents=True, exist_ok=True)
        a = np.clip(amap, 0, 1)
        a = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).resize((frame.shape[1], frame.shape[0])))
        over = frame.astype(np.float32).copy()
        over[..., 0] = np.clip(over[..., 0] * 0.5 + a * 0.8, 0, 255)
        p = self.heatmap_dir / f"brick{self.brick_idx}_{view}_{int(time.time() * 1000)}.png"
        Image.fromarray(over.astype(np.uint8)).save(p)
        return str(p)
