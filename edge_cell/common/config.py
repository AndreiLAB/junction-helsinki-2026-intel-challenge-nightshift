"""Load configs/station.yaml. Paths in it are relative to the repo root."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]


def load_station(path: str | Path | None = None) -> dict:
    p = Path(path) if path else ROOT / "configs" / "station.yaml"
    with open(p) as f:
        return yaml.safe_load(f)


def repo_path(rel: str | Path) -> Path:
    p = Path(rel)
    return p if p.is_absolute() else ROOT / p
