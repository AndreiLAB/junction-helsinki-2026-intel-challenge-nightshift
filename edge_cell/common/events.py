"""Event log: runs/<run_id>/events.jsonl, one JSON object per line (see docs/CONTRACTS.md)."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from common.config import ROOT


def new_run_id(tag: str = "") -> str:
    rid = time.strftime("%Y%m%d-%H%M%S")
    return f"{rid}-{tag}" if tag else rid


def _jsonable(o):
    try:
        import numpy as np
        if isinstance(o, np.ndarray):
            return [round(float(x), 3) for x in o.ravel()]
        if isinstance(o, np.generic):
            return o.item()
    except ImportError:
        pass
    return str(o)


class EventLog:
    def __init__(self, run_id: str, runs_dir: Path | None = None, echo: bool = False):
        self.run_id = run_id
        self.dir = (runs_dir or ROOT / "runs") / run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "events.jsonl"
        self._f = open(self.path, "a", buffering=1)
        self._lock = threading.Lock()
        self.echo = echo
        self.events: list[dict] = []

    def log(self, brick_idx: int, state: str, event: str, data: dict | None = None, ts: float | None = None):
        rec = {"ts": round(ts if ts is not None else time.time(), 3), "run_id": self.run_id,
               "brick_idx": brick_idx, "state": state, "event": event, "data": data or {}}
        line = json.dumps(rec, default=_jsonable)
        with self._lock:
            self._f.write(line + "\n")
            self.events.append(json.loads(line))
        if self.echo:
            print(f"[{state:>14}] brick {brick_idx}: {event} {data or ''}", flush=True)
        return rec

    def close(self):
        self._f.close()
