"""Train an Anomalib model on good inspect-camera frames, test on held-out good + defect, export OpenVINO.
Run with the separate venv:  .venv-anomalib/bin/python -m inspection.train [patchcore|padim] [data_root] [name]"""
import json
import sys
import time
from pathlib import Path

import torch

torch.set_num_threads(6)   # leave CPU for Studio recording

from anomalib.data import Folder
from anomalib.deploy import ExportType
from anomalib.engine import Engine
from anomalib.models import Padim, Patchcore

ROOT = Path(__file__).resolve().parent.parent


def main(model_name="patchcore", data_root="data/inspect_frames/v1", name=None):
    name = name or f"{model_name}_v1"
    out = ROOT / "models/anomaly" / name
    dm = Folder(name="duplo", root=ROOT / data_root, normal_dir="train_good", abnormal_dir="defect",
                normal_test_dir="test_good", train_batch_size=16, eval_batch_size=16, num_workers=2, seed=0)
    model = Patchcore(coreset_sampling_ratio=0.1) if model_name == "patchcore" else Padim()
    engine = Engine(accelerator="cpu", devices=1, default_root_dir=ROOT / "runs/anomalib", logger=False)
    t = time.time(); engine.fit(model=model, datamodule=dm); fit_s = time.time() - t
    res = engine.test(model=model, datamodule=dm)[0]
    p = engine.export(model=model, export_type=ExportType.OPENVINO, export_root=out)
    card = {"name": name, "model": model_name, "anomalib": "2.7.0", "trained_on": data_root + "/train_good",
            "train_device": "CPU", "fit_s": round(fit_s, 1), "test": {k: float(v) for k, v in res.items()},
            "export": str(p), "evidence": "REPLAY (frames cut from duplo_v1 demos, held-out by episode)"}
    (out / "MODEL_CARD.json").write_text(json.dumps(card, indent=1))
    print(json.dumps(card, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:])
