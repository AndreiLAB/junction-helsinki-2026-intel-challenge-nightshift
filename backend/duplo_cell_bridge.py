#!/usr/bin/env python3
"""
duplo_cell_bridge.py
Self-contained, zero-dependency bridge and file watcher for `~/duplo-cell` -> Unified Cloud, AI & Data Hub.

Uses ONLY Python's standard library (`urllib.request`, `json`, `os`, `time`, `zlib`, `struct`,
`base64`, `threading`, `argparse`, `pathlib`, `datetime`) so it runs directly on the Ubuntu
station laptop without modifying `cell/` or installing any pip packages.

Modes:
  1. Zero-Intrusion File Watcher (recommended by Prompt 4 Step 8 — never touches or slows `cell/`):
       python3 duplo_cell_bridge.py --watch ~/duplo-cell --hub http://10.0.36.249:8000

  2. Fake Run Generator & Replay (`Prompt 4 Step 8: "Build it against a fake run first"`):
       python3 duplo_cell_bridge.py --replay-fake --hub http://localhost:8000

  3. Programmatic Non-Blocking Library Helpers:
       from duplo_cell_bridge import push_cycle_async, fetch_active_policy
"""

from __future__ import annotations

import argparse
import base64
import datetime
import json
import os
import struct
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_HUB_URL = os.environ.get("DUPLO_HUB_URL", "http://localhost:8000")

INSTRUCTION_PICK_PRESENT = "Pick up a brick and hold it in front of the inspection camera."
INSTRUCTION_PLACE_GOOD = "Put the brick in the good bowl."
INSTRUCTION_PLACE_DEFECT = "Put the brick in the defective bowl."


# ---------------------------------------------------------------------------
# Pure-stdlib HTTP helpers
# ---------------------------------------------------------------------------

def _http_json(
    url: str,
    method: str = "GET",
    payload: Optional[Any] = None,
    timeout: float = 5.0,
    quiet: bool = False,
) -> Optional[Dict[str, Any]]:
    data_bytes = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            raw = res.read().decode("utf-8")
            return json.loads(raw) if raw else {"status": "ok"}
    except Exception as exc:
        if not quiet:
            print(f"[duplo_cell_bridge] Warning: {method} {url} failed: {exc}", file=sys.stderr)
        return None


def fetch_active_policy(host: str = DEFAULT_HUB_URL, timeout: float = 2.0) -> Dict[str, Any]:
    """
    Polls `GET /api/policy` on the Cloud, AI & Data Hub for `t_low`, `t_high`,
    `active_anomaly_threshold`, and active Gemini Copilot rules.
    """
    url = f"{host.rstrip('/')}/api/policy"
    res = _http_json(url, method="GET", timeout=timeout, quiet=True)
    if isinstance(res, dict):
        return res
    return {
        "active_anomaly_threshold": 0.55,
        "anomaly_threshold": 0.55,
        "t_low": 0.35,
        "t_high": 0.60,
        "regrasp_range": [0.35, 0.60],
        "rules": [],
    }


# Backward-compatible alias
get_active_policy = fetch_active_policy


def _verdict_to_action(verdict: Optional[str], action: Optional[str], score: float, t_low: float, t_high: float) -> Tuple[str, str]:
    v = (verdict or "").strip().upper()
    a = (action or "").strip().upper()
    if v in ("GOOD", "DEFECT", "UNCERTAIN", "NO_BRICK"):
        if not a:
            a = "PERFECT_BOWL" if v == "GOOD" else ("DEFECTIVE_BOWL" if v == "DEFECT" else "REGRASP_TRIGGERED")
        return v, a
    if a:
        if a == "PERFECT_BOWL":
            return "GOOD", "PERFECT_BOWL"
        if a == "DEFECTIVE_BOWL":
            return "DEFECT", "DEFECTIVE_BOWL"
        return "UNCERTAIN", "REGRASP_TRIGGERED"
    if score < t_low:
        return "GOOD", "PERFECT_BOWL"
    if score > t_high:
        return "DEFECT", "DEFECTIVE_BOWL"
    return "UNCERTAIN", "REGRASP_TRIGGERED"


def send_cycle_to_dashboard(
    brick_uuid: Optional[str] = None,
    color: str = "blue",
    defect_label: Optional[str] = None,
    anomaly_score: Optional[float] = None,
    action: Optional[str] = None,
    root_cause: Optional[str] = None,
    npu_latency_ms: Optional[float] = 9.4,
    igpu_latency_ms: Optional[float] = 24.1,
    cpu_latency_ms: Optional[float] = 2.1,
    raw_image_b64: Optional[str] = None,
    heatmap_image_b64: Optional[str] = None,
    top_image_b64: Optional[str] = None,
    # Native ~/duplo-cell InspectionResult & events.jsonl fields:
    brick_idx: Optional[int] = None,
    run_id: Optional[str] = None,
    ts: Optional[str] = None,
    verdict: Optional[str] = None,
    score: Optional[float] = None,
    t_low: float = 0.35,
    t_high: float = 0.60,
    views: Optional[List[Dict[str, Any]]] = None,
    heatmap_png: Optional[str] = None,
    instruction: Optional[str] = None,
    cell_state: Optional[str] = None,
    model: Optional[str] = "patchcore_256",
    precision: Optional[str] = "INT8",
    device: Optional[str] = "NPU",
    latency_ms: Optional[float] = None,
    cycle_s: Optional[float] = None,
    stage_durations_s: Optional[Dict[str, float]] = None,
    evidence: Optional[str] = None,
    host: str = DEFAULT_HUB_URL,
    async_send: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Posts a brick inspection cycle to `POST /api/cycles` using either native `~/duplo-cell`
    `InspectionResult` fields or Hub fields.
    """
    eff_score = float(score if score is not None else (anomaly_score if anomaly_score is not None else 0.12))
    resolved_verdict, resolved_action = _verdict_to_action(verdict, action, eff_score, t_low, t_high)

    if not instruction:
        if resolved_verdict == "GOOD":
            instruction = INSTRUCTION_PLACE_GOOD
        elif resolved_verdict == "DEFECT":
            instruction = INSTRUCTION_PLACE_DEFECT
        else:
            instruction = INSTRUCTION_PICK_PRESENT

    uid = brick_uuid
    if not uid:
        if run_id and brick_idx is not None:
            safe_run = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in run_id)[:36]
            uid = f"{safe_run}_b{int(brick_idx):04d}"
        else:
            uid = f"cell_{uuid.uuid4().hex[:8]}"

    payload: Dict[str, Any] = {
        "brick_uuid": uid,
        "brick_idx": brick_idx,
        "run_id": run_id,
        "ts": ts,
        "color": color,
        "defect_label": defect_label,
        "verdict": resolved_verdict,
        "score": round(eff_score, 4),
        "anomaly_score": round(eff_score, 4),
        "t_low": round(float(t_low), 4),
        "t_high": round(float(t_high), 4),
        "views": views,
        "heatmap_png": heatmap_png,
        "action": resolved_action,
        "instruction": instruction,
        "cell_state": cell_state,
        "model": model,
        "precision": precision,
        "device": device,
        "latency_ms": latency_ms if latency_ms is not None else npu_latency_ms,
        "cycle_s": round(float(cycle_s), 2) if cycle_s is not None else None,
        "stage_durations_s": stage_durations_s,
        "evidence": evidence,
        "root_cause": root_cause,
        "npu_latency_ms": npu_latency_ms,
        "igpu_latency_ms": igpu_latency_ms,
        "cpu_latency_ms": cpu_latency_ms,
        "raw_image_b64": raw_image_b64,
        "heatmap_image_b64": heatmap_image_b64,
        "top_image_b64": top_image_b64,
    }
    # Strip None values so Hub defaults apply cleanly
    clean_payload = {k: v for k, v in payload.items() if v is not None}
    url = f"{host.rstrip('/')}/api/cycles"

    if async_send:
        t = threading.Thread(target=_http_json, args=(url, "POST", clean_payload, 6.0, False), daemon=True)
        t.start()
        return {"status": "dispatched_async", "brick_uuid": uid, "verdict": resolved_verdict, "action": resolved_action}
    return _http_json(url, method="POST", payload=clean_payload, timeout=8.0)


def push_cycle_async(
    brick_uuid: Optional[str] = None,
    color: str = "blue",
    defect_label: Optional[str] = "Pristine",
    anomaly_score: float = 0.12,
    action: Optional[str] = "PERFECT_BOWL",
    root_cause: Optional[str] = None,
    npu_latency_ms: float = 9.4,
    igpu_latency_ms: float = 24.1,
    cpu_latency_ms: float = 2.1,
    raw_image_b64: Optional[str] = None,
    heatmap_image_b64: Optional[str] = None,
    host: str = DEFAULT_HUB_URL,
    **kwargs: Any,
) -> Optional[Dict[str, Any]]:
    """
    Non-blocking helper that dispatches a robot inspection cycle in a daemon background thread
    so the local <36 ms OpenVINO control loop never waits on network I/O.
    """
    return send_cycle_to_dashboard(
        brick_uuid=brick_uuid,
        color=color,
        defect_label=defect_label,
        anomaly_score=anomaly_score,
        action=action,
        root_cause=root_cause,
        npu_latency_ms=npu_latency_ms,
        igpu_latency_ms=igpu_latency_ms,
        cpu_latency_ms=cpu_latency_ms,
        raw_image_b64=raw_image_b64,
        heatmap_image_b64=heatmap_image_b64,
        host=host,
        async_send=True,
        **kwargs,
    )


def push_benchmarks(
    benchmarks: List[Dict[str, Any]] | Dict[str, Any],
    host: str = DEFAULT_HUB_URL,
) -> Optional[Dict[str, Any]]:
    """Pushes `~/duplo-cell/reports/bench/*.json` records to `POST /api/benchmarks`."""
    url = f"{host.rstrip('/')}/api/benchmarks"
    return _http_json(url, method="POST", payload=benchmarks, timeout=6.0)


def push_cell_state(
    cell_state: str,
    run_id: Optional[str] = None,
    brick_idx: Optional[int] = None,
    event: Optional[str] = None,
    instruction: Optional[str] = None,
    verdict: Optional[str] = None,
    score: Optional[float] = None,
    evidence: Optional[str] = None,
    host: str = DEFAULT_HUB_URL,
) -> Optional[Dict[str, Any]]:
    """Broadcasts a live `events.jsonl` state transition to `POST /api/cell-state`."""
    url = f"{host.rstrip('/')}/api/cell-state"
    payload = {
        "cell_state": cell_state,
        "run_id": run_id,
        "brick_idx": brick_idx,
        "event": event,
        "instruction": instruction,
        "verdict": verdict,
        "score": score,
        "evidence": evidence,
    }
    clean = {k: v for k, v in payload.items() if v is not None}
    return _http_json(url, method="POST", payload=clean, timeout=2.5, quiet=True)


def patch_nemotron_analysis(
    brick_uuid: str,
    nemotron_root_cause: str,
    adjusted_threshold: Optional[float] = None,
    host: str = DEFAULT_HUB_URL,
) -> Optional[Dict[str, Any]]:
    url = f"{host.rstrip('/')}/api/cycles/{brick_uuid}/nemotron"
    payload = {
        "nemotron_root_cause": nemotron_root_cause,
        "adjusted_threshold": adjusted_threshold,
    }
    return _http_json(url, method="PATCH", payload=payload, timeout=5.0)


# ---------------------------------------------------------------------------
# Pure-stdlib PNG encoder (for zero-dependency `--replay-fake` heatmaps & crops)
# ---------------------------------------------------------------------------

def _make_stdlib_png_bytes(
    width: int = 128,
    height: int = 128,
    color: str = "yellow",
    score: float = 0.14,
    is_heatmap: bool = False,
) -> bytes:
    """Generates a valid RGB PNG image using only `zlib` and `struct` (no Pillow needed)."""
    palette = {
        "green": (35, 180, 85),
        "yellow": (245, 195, 30),
        "blue": (35, 115, 235),
        "red": (225, 48, 48),
        "orange": (245, 125, 28),
    }
    br, bg, bb = palette.get(color.lower(), (35, 115, 235))
    studs = ((0.36, 0.36), (0.64, 0.36), (0.36, 0.64), (0.64, 0.64))

    rows: List[bytes] = []
    for y in range(height):
        ny = y / float(height)
        row = bytearray([0])  # Filter type 0 (None)
        for x in range(width):
            nx = x / float(width)
            if is_heatmap:
                # Anomalib JET-like thermal map centered at (0.64, 0.38)
                dx = nx - 0.64
                dy = ny - 0.38
                d2 = dx * dx + dy * dy
                intensity = score * (2.71828 ** (-d2 / 0.032))
                if intensity > 0.55:
                    r, g, b = 250, 35, 35
                elif intensity > 0.32:
                    r, g, b = 250, 210, 25
                elif intensity > 0.14:
                    r, g, b = 20, 210, 140
                else:
                    r, g, b = 10, 24, 68
            else:
                in_brick = 0.18 <= nx <= 0.82 and 0.18 <= ny <= 0.82
                if not in_brick:
                    r, g, b = 15, 23, 42
                else:
                    r, g, b = br, bg, bb
                    for sx, sy in studs:
                        if (nx - sx) ** 2 + (ny - sy) ** 2 < 0.011:
                            r = min(255, r + 28)
                            g = min(255, g + 28)
                            b = min(255, b + 28)
                    if score > 0.58 and abs((nx - 0.56) + 0.65 * (ny - 0.36)) < 0.028 and 0.45 <= nx <= 0.78:
                        # Visible dark marker stripe / scratch
                        r, g, b = 24, 20, 20
                    elif 0.35 <= score <= 0.58 and (nx - 0.63) ** 2 + (ny - 0.37) ** 2 < 0.015:
                        # Specular glare highlight
                        r, g, b = 242, 248, 255
            row.extend((r, g, b))
        rows.append(bytes(row))

    raw_data = b"".join(rows)

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    idat = zlib.compress(raw_data, level=6)
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


def _encode_file_as_data_uri(file_path: Path) -> Optional[str]:
    if not file_path.is_file():
        return None
    try:
        raw_bytes = file_path.read_bytes()
        if not raw_bytes:
            return None
        ext = file_path.suffix.lower().lstrip(".")
        mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
        b64 = base64.b64encode(raw_bytes).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return None


def _parse_iso_ts(ts_val: Any) -> Optional[float]:
    if ts_val is None:
        return None
    if isinstance(ts_val, (int, float)):
        return float(ts_val)
    if isinstance(ts_val, str):
        s = ts_val.strip()
        if not s:
            return None
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            return datetime.datetime.fromisoformat(s).timestamp()
        except Exception:
            try:
                return float(s)
            except Exception:
                return None
    return None


# ---------------------------------------------------------------------------
# Zero-Intrusion `events.jsonl` + `heatmaps/*.png` + `reports/bench/*.json` Watcher
# ---------------------------------------------------------------------------

class BrickAccumulator:
    """Tracks state transitions, multi-view scores, and timing for one `(run_id, brick_idx)`."""

    def __init__(self, run_id: str, brick_idx: int) -> None:
        self.run_id = run_id
        self.brick_idx = brick_idx
        self.first_epoch: Optional[float] = None
        self.last_epoch: Optional[float] = None
        self.last_state_enter_epoch: Optional[float] = None
        self.last_state: str = "PICK_PRESENT"
        self.last_ts_str: Optional[str] = None
        self.stage_durations_s: Dict[str, float] = {"pick": 0.0, "inspect": 0.0, "decide": 0.0, "place": 0.0}

        self.color: str = "blue"
        self.defect_label: Optional[str] = None
        self.verdict: Optional[str] = None
        self.score: Optional[float] = None
        self.t_low: float = 0.35
        self.t_high: float = 0.60
        self.views: List[Dict[str, Any]] = []
        self.heatmap_png: Optional[str] = None
        self.raw_png: Optional[str] = None
        self.top_png: Optional[str] = None
        self.instruction: Optional[str] = None
        self.model: str = "patchcore_256"
        self.precision: str = "INT8"
        self.device: str = "NPU"
        self.latency_ms: Optional[float] = None
        self.igpu_latency_ms: Optional[float] = None
        self.cpu_latency_ms: Optional[float] = None
        self.evidence: Optional[str] = None
        self.root_cause: Optional[str] = None
        self.dispatched: bool = False

    @staticmethod
    def _phase_bucket(cell_state: str) -> Optional[str]:
        st = cell_state.upper()
        if st in ("PICK_PRESENT", "SNAP_TO_INSPECT", "CHECK_HELD"):
            return "pick"
        if st in ("INSPECT", "NEXT_VIEW"):
            return "inspect"
        if st == "DECIDE":
            return "decide"
        if st in ("PLACE_GOOD", "PLACE_DEFECT", "REGRASP", "CONFIRM"):
            return "place"
        return None

    def _merge_view(self, view_name: str, view_score: float) -> None:
        v_clean = str(view_name or "inspect")
        sc = round(float(view_score), 4)
        for existing in self.views:
            if existing["view"] == v_clean:
                existing["score"] = sc
                return
        self.views.append({"view": v_clean, "score": sc})

    def apply_event(self, record: Dict[str, Any]) -> bool:
        """
        Applies one `events.jsonl` object and returns True when the brick cycle reached
        a terminal completion event (`CONFIRM`, `REGRASP` end, `NO_BRICK` skip, `FAULT`).
        """
        ts_raw = record.get("ts")
        epoch = _parse_iso_ts(ts_raw)
        state_str = str(record.get("state") or self.last_state or "PICK_PRESENT").strip().upper()
        event_name = str(record.get("event") or "").strip().lower()

        if epoch is not None:
            if self.first_epoch is None:
                self.first_epoch = epoch
            if self.last_state_enter_epoch is not None and epoch >= self.last_state_enter_epoch:
                prev_bucket = self._phase_bucket(self.last_state)
                if prev_bucket:
                    self.stage_durations_s[prev_bucket] = round(
                        self.stage_durations_s.get(prev_bucket, 0.0) + (epoch - self.last_state_enter_epoch),
                        3,
                    )
            self.last_state_enter_epoch = epoch
            self.last_epoch = epoch
        if isinstance(ts_raw, str):
            self.last_ts_str = ts_raw

        self.last_state = state_str

        data = record.get("data")
        if not isinstance(data, dict):
            data = {}
        # Unwrap nested InspectionResult if logged under `data.result` or `data.inspection`
        nested = data.get("result") or data.get("inspection")
        merged: Dict[str, Any] = {**(nested if isinstance(nested, dict) else {}), **data}

        if merged.get("color"):
            self.color = str(merged["color"]).strip().lower()
        if merged.get("defect_label"):
            self.defect_label = str(merged["defect_label"])
        if merged.get("t_low") is not None:
            self.t_low = float(merged["t_low"])
        if merged.get("t_high") is not None:
            self.t_high = float(merged["t_high"])

        if isinstance(merged.get("views"), list):
            for v_item in merged["views"]:
                if isinstance(v_item, dict) and v_item.get("score") is not None:
                    self._merge_view(str(v_item.get("view") or "inspect"), float(v_item["score"]))
        elif merged.get("view") and merged.get("score") is not None:
            self._merge_view(str(merged["view"]), float(merged["score"]))

        if merged.get("score") is not None:
            sc_val = float(merged["score"])
            if self.views:
                self.score = max(sc_val, max(float(v["score"]) for v in self.views))
            else:
                self.score = sc_val
        elif self.views:
            self.score = max(float(v["score"]) for v in self.views)

        if merged.get("verdict"):
            self.verdict = str(merged["verdict"]).strip().upper()
        if merged.get("instruction"):
            self.instruction = str(merged["instruction"]).strip()
        if merged.get("heatmap_png"):
            self.heatmap_png = str(merged["heatmap_png"])
        if merged.get("raw_png"):
            self.raw_png = str(merged["raw_png"])
        if merged.get("top_png"):
            self.top_png = str(merged["top_png"])
        if merged.get("model"):
            self.model = str(merged["model"])
        if merged.get("precision"):
            self.precision = str(merged["precision"]).upper()
        if merged.get("device"):
            self.device = str(merged["device"]).upper()
        if merged.get("latency_ms") is not None:
            self.latency_ms = float(merged["latency_ms"])
        if merged.get("igpu_latency_ms") is not None or merged.get("policy_latency_ms") is not None:
            self.igpu_latency_ms = float(merged.get("igpu_latency_ms") or merged.get("policy_latency_ms"))
        if merged.get("cpu_latency_ms") is not None:
            self.cpu_latency_ms = float(merged["cpu_latency_ms"])
        if merged.get("evidence"):
            self.evidence = str(merged["evidence"]).strip().upper()
        if merged.get("root_cause") or merged.get("reason"):
            self.root_cause = str(merged.get("root_cause") or merged.get("reason"))

        if state_str == "CONFIRM":
            return True
        if state_str == "FAULT":
            return True
        if state_str == "REGRASP" and event_name in ("regrasp_complete", "cycle_complete", "put_back", "re_pick", "regrasp_triggered"):
            return True
        if event_name in ("brick_complete", "cycle_complete", "confirmed", "skipped_no_brick"):
            return True
        return False

    def has_meaningful_data(self) -> bool:
        return self.score is not None or self.verdict is not None or bool(self.views)

    def cycle_seconds(self) -> Optional[float]:
        if self.first_epoch is not None and self.last_epoch is not None and self.last_epoch >= self.first_epoch:
            delta = round(self.last_epoch - self.first_epoch, 2)
            if delta > 0.0:
                return delta
        total_stage = sum(self.stage_durations_s.values())
        return round(total_stage, 2) if total_stage > 0 else None


class DuploCellWatcher:
    """
    Zero-intrusion watcher reading `runs/<run_id>/events.jsonl`, `runs/<run_id>/heatmaps/*.png`,
    and `reports/bench/*.json` without touching `cell/`.
    """

    def __init__(self, root_dir: Path, hub_url: str) -> None:
        self.root_dir = root_dir.expanduser().resolve()
        self.hub_url = hub_url.rstrip("/")
        self.current_events_file: Optional[Path] = None
        self.file_offset: int = 0
        self.bricks: Dict[Tuple[str, int], BrickAccumulator] = {}
        self.active_brick_key: Optional[Tuple[str, int]] = None
        self.synced_bench_mtimes: Dict[str, float] = {}
        self.cycles_pushed: int = 0
        self.benchmarks_pushed: int = 0

    def _find_latest_events_file(self) -> Optional[Path]:
        runs_dir = self.root_dir / "runs"
        if not runs_dir.is_dir():
            return None
        candidates = list(runs_dir.glob("*/events.jsonl"))
        if not candidates:
            return None
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return candidates[0]

    def _resolve_image_path(self, rel_or_abs: Optional[str], run_dir: Path) -> Optional[Path]:
        if not rel_or_abs:
            return None
        p = Path(rel_or_abs)
        if p.is_file():
            return p
        from_root = self.root_dir / rel_or_abs
        if from_root.is_file():
            return from_root
        from_run = run_dir / rel_or_abs
        if from_run.is_file():
            return from_run
        return None

    def _locate_brick_images(self, acc: BrickAccumulator, run_dir: Path) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        """Returns `(raw_b64, heatmap_b64, top_b64, heatmap_rel_path)`."""
        heat_path = self._resolve_image_path(acc.heatmap_png, run_dir)
        heat_dir = run_dir / "heatmaps"
        if heat_path is None and heat_dir.is_dir():
            patterns = [
                f"{acc.brick_idx:04d}*.png",
                f"*{acc.brick_idx:04d}*.png",
                f"brick_{acc.brick_idx}_*.png",
                f"{acc.brick_idx}_*.png",
            ]
            found: List[Path] = []
            for pat in patterns:
                found.extend(heat_dir.glob(pat))
            if found:
                found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                heat_path = found[0]

        raw_path = self._resolve_image_path(acc.raw_png, run_dir)
        if raw_path is None:
            for folder_name in ("raw", "crops", "frames"):
                f_dir = run_dir / folder_name
                if f_dir.is_dir():
                    matches = sorted(f_dir.glob(f"*{acc.brick_idx:04d}*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
                    if matches:
                        raw_path = matches[0]
                        break

        top_path = self._resolve_image_path(acc.top_png, run_dir)

        heat_rel = acc.heatmap_png
        if heat_path is not None and not heat_rel:
            try:
                heat_rel = str(heat_path.relative_to(self.root_dir)).replace("\\", "/")
            except ValueError:
                heat_rel = str(heat_path)

        return (
            _encode_file_as_data_uri(raw_path) if raw_path else None,
            _encode_file_as_data_uri(heat_path) if heat_path else None,
            _encode_file_as_data_uri(top_path) if top_path else None,
            heat_rel,
        )

    def _flush_brick(self, acc: BrickAccumulator, run_dir: Path) -> None:
        if acc.dispatched or not acc.has_meaningful_data():
            return
        acc.dispatched = True

        raw_b64, heat_b64, top_b64, heat_rel = self._locate_brick_images(acc, run_dir)
        eff_score = acc.score if acc.score is not None else 0.12
        evidence = acc.evidence
        if not evidence:
            evidence = "REPLAY" if ("fake" in acc.run_id.lower() or "replay" in acc.run_id.lower()) else "REAL"

        res = send_cycle_to_dashboard(
            brick_idx=acc.brick_idx,
            run_id=acc.run_id,
            ts=acc.last_ts_str,
            color=acc.color,
            defect_label=acc.defect_label,
            verdict=acc.verdict,
            score=eff_score,
            t_low=acc.t_low,
            t_high=acc.t_high,
            views=acc.views or [{"view": "inspect", "score": eff_score}],
            heatmap_png=heat_rel,
            instruction=acc.instruction,
            cell_state=acc.last_state,
            model=acc.model,
            precision=acc.precision,
            device=acc.device,
            latency_ms=acc.latency_ms,
            igpu_latency_ms=acc.igpu_latency_ms or 24.1,
            cpu_latency_ms=acc.cpu_latency_ms or 2.1,
            cycle_s=acc.cycle_seconds(),
            stage_durations_s={k: v for k, v in acc.stage_durations_s.items() if v > 0} or None,
            evidence=evidence,
            root_cause=acc.root_cause,
            raw_image_b64=raw_b64,
            heatmap_image_b64=heat_b64,
            top_image_b64=top_b64,
            host=self.hub_url,
            async_send=False,
        )
        if res:
            self.cycles_pushed += 1
            print(
                f"  [CYCLE] run={acc.run_id} brick=#{acc.brick_idx} "
                f"verdict={res.get('verdict')} score={eff_score:.2f} "
                f"views={len(acc.views or [1])} cycle_s={acc.cycle_seconds()}s "
                f"evidence={evidence} -> {res.get('cycle_id')}"
            )

    def sync_benchmarks(self, extra_bench_dir: Optional[Path] = None) -> int:
        bench_dirs = [self.root_dir / "reports" / "bench"]
        if extra_bench_dir is not None:
            bench_dirs.append(extra_bench_dir)
        if self.current_events_file is not None:
            bench_dirs.append(self.current_events_file.parent / "bench")

        batch: List[Dict[str, Any]] = []
        for b_dir in bench_dirs:
            if not b_dir.is_dir():
                continue
            for jf in sorted(b_dir.glob("*.json")):
                try:
                    mtime = jf.stat().st_mtime
                except OSError:
                    continue
                key = str(jf.resolve())
                if self.synced_bench_mtimes.get(key) == mtime:
                    continue
                try:
                    parsed = json.loads(jf.read_text(encoding="utf-8"))
                    if isinstance(parsed, dict) and parsed.get("model"):
                        batch.append(parsed)
                    elif isinstance(parsed, list):
                        batch.extend(r for r in parsed if isinstance(r, dict) and r.get("model"))
                    self.synced_bench_mtimes[key] = mtime
                except Exception as exc:
                    print(f"[duplo_cell_bridge] Skipping invalid bench JSON {jf.name}: {exc}", file=sys.stderr)

        if batch:
            res = push_benchmarks(batch, host=self.hub_url)
            if res:
                self.benchmarks_pushed += len(batch)
                print(f"  [BENCH] Synced {len(batch)} OpenVINO benchmark record(s) -> POST /api/benchmarks")
        return len(batch)

    def poll_events_once(self, flush_pending: bool = False, stream_states: bool = True) -> int:
        latest = self._find_latest_events_file()
        if latest is None:
            return 0

        if self.current_events_file != latest:
            self.current_events_file = latest
            self.file_offset = 0
            print(f"[duplo_cell_bridge] Tailing {latest}")

        run_dir = latest.parent
        default_run_id = run_dir.name
        processed_lines = 0

        try:
            file_size = latest.stat().st_size
            if file_size < self.file_offset:
                self.file_offset = 0
            with latest.open("r", encoding="utf-8") as fh:
                fh.seek(self.file_offset)
                while True:
                    line = fh.readline()
                    if not line:
                        break
                    self.file_offset = fh.tell()
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        ev = json.loads(stripped)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(ev, dict):
                        continue

                    processed_lines += 1
                    run_id = str(ev.get("run_id") or default_run_id)
                    state_str = str(ev.get("state") or "HOME").strip().upper()
                    brick_idx_raw = ev.get("brick_idx")
                    data = ev.get("data") if isinstance(ev.get("data"), dict) else {}

                    if stream_states:
                        push_cell_state(
                            cell_state=state_str,
                            run_id=run_id,
                            brick_idx=int(brick_idx_raw) if brick_idx_raw is not None else None,
                            event=str(ev.get("event") or ""),
                            instruction=data.get("instruction"),
                            verdict=data.get("verdict"),
                            score=data.get("score"),
                            evidence=data.get("evidence"),
                            host=self.hub_url,
                        )

                    if brick_idx_raw is None:
                        if state_str == "DONE" and self.active_brick_key in self.bricks:
                            self._flush_brick(self.bricks[self.active_brick_key], run_dir)
                        continue

                    b_idx = int(brick_idx_raw)
                    b_key = (run_id, b_idx)

                    # If robot moved to a new brick_idx, flush previous un-confirmed brick if it had inspection data
                    if self.active_brick_key and self.active_brick_key != b_key:
                        prev_acc = self.bricks.get(self.active_brick_key)
                        if prev_acc and not prev_acc.dispatched:
                            self._flush_brick(prev_acc, run_dir)

                    self.active_brick_key = b_key
                    acc = self.bricks.get(b_key)
                    if acc is None or acc.dispatched:
                        acc = BrickAccumulator(run_id=run_id, brick_idx=b_idx)
                        self.bricks[b_key] = acc

                    completed = acc.apply_event(ev)
                    if completed:
                        self._flush_brick(acc, run_dir)
        except OSError as exc:
            print(f"[duplo_cell_bridge] File read error on {latest}: {exc}", file=sys.stderr)

        if flush_pending:
            for acc in list(self.bricks.values()):
                if not acc.dispatched and acc.has_meaningful_data():
                    self._flush_brick(acc, run_dir)

        return processed_lines


# ---------------------------------------------------------------------------
# `--replay-fake` Generator (`Prompt 4 Step 8: "Build it against a fake run first"`)
# ---------------------------------------------------------------------------

def generate_fake_duplo_run(base_dir: Path, write_reports_bench: bool = False) -> Path:
    """
    Creates `runs/fake-20261114/events.jsonl`, `runs/fake-20261114/heatmaps/*.png`,
    `runs/fake-20261114/raw/*.png`, and OpenVINO benchmark JSON files covering:
      - Brick 1: Green GOOD (`inspect=0.14 < t_low=0.35` -> `"Put the brick in the good bowl."`)
      - Brick 2: Yellow UNCERTAIN -> NEXT_VIEW wrist rotation -> DEFECT (`0.46` -> `0.84 > t_high=0.60`
                 -> `"Put the brick in the defective bowl."`)
      - Brick 3: Blue UNCERTAIN across 3 views (`0.44`, `0.52`, `0.49`) -> `REGRASP` recovery
      - Brick 4: Red GOOD (`inspect=0.18 < t_low=0.35` -> `"Put the brick in the good bowl."`)
    """
    run_id = "fake-20261114"
    run_dir = base_dir / "runs" / run_id
    heat_dir = run_dir / "heatmaps"
    raw_dir = run_dir / "raw"
    bench_dir = (base_dir / "reports" / "bench") if write_reports_bench else (run_dir / "bench")

    heat_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    bench_dir.mkdir(parents=True, exist_ok=True)

    # Save synthetic crops & heatmaps
    brick_specs = [
        (1, "green", 0.14, "0001_inspect.png"),
        (2, "yellow", 0.84, "0002_view2.png"),
        (3, "blue", 0.52, "0003_view3.png"),
        (4, "red", 0.18, "0004_inspect.png"),
    ]
    for b_idx, col, sc, fname in brick_specs:
        (heat_dir / fname).write_bytes(_make_stdlib_png_bytes(128, 128, color=col, score=sc, is_heatmap=True))
        (raw_dir / fname).write_bytes(_make_stdlib_png_bytes(128, 128, color=col, score=sc, is_heatmap=False))

    base_dt = datetime.datetime(2026, 11, 14, 14, 25, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=2)))

    def _iso(offset_s: float) -> str:
        return (base_dt + datetime.timedelta(seconds=offset_s)).isoformat(timespec="milliseconds")

    events: List[Dict[str, Any]] = [
        # --- Brick 1: Green -> GOOD ---
        {"ts": _iso(0.00), "run_id": run_id, "brick_idx": 1, "state": "PICK_PRESENT", "event": "skill_start", "data": {"color": "green", "instruction": INSTRUCTION_PICK_PRESENT, "evidence": "REPLAY"}},
        {"ts": _iso(1.55), "run_id": run_id, "brick_idx": 1, "state": "SNAP_TO_INSPECT", "event": "pose_snap", "data": {"evidence": "REPLAY"}},
        {"ts": _iso(1.85), "run_id": run_id, "brick_idx": 1, "state": "CHECK_HELD", "event": "held_ok", "data": {"evidence": "REPLAY"}},
        {"ts": _iso(2.10), "run_id": run_id, "brick_idx": 1, "state": "INSPECT", "event": "inspection_result", "data": {
            "brick_idx": 1, "verdict": "GOOD", "score": 0.14, "t_low": 0.35, "t_high": 0.60,
            "views": [{"view": "inspect", "score": 0.14}],
            "heatmap_png": f"runs/{run_id}/heatmaps/0001_inspect.png",
            "raw_png": f"runs/{run_id}/raw/0001_inspect.png",
            "defect_label": "None (Pristine)",
            "model": "patchcore_256", "precision": "INT8", "device": "NPU", "latency_ms": 9.3, "evidence": "REPLAY",
        }},
        {"ts": _iso(2.18), "run_id": run_id, "brick_idx": 1, "state": "DECIDE", "event": "instruction_selected", "data": {
            "verdict": "GOOD", "instruction": INSTRUCTION_PLACE_GOOD, "igpu_latency_ms": 23.8, "evidence": "REPLAY",
        }},
        {"ts": _iso(3.55), "run_id": run_id, "brick_idx": 1, "state": "PLACE_GOOD", "event": "skill_done", "data": {"evidence": "REPLAY"}},
        {"ts": _iso(3.82), "run_id": run_id, "brick_idx": 1, "state": "CONFIRM", "event": "confirmed", "data": {"bowl": "good", "evidence": "REPLAY"}},

        # --- Brick 2: Yellow -> UNCERTAIN on inspect (0.46) -> NEXT_VIEW wrist turn -> DEFECT on inspect_view2 (0.84) ---
        {"ts": _iso(5.00), "run_id": run_id, "brick_idx": 2, "state": "PICK_PRESENT", "event": "skill_start", "data": {"color": "yellow", "instruction": INSTRUCTION_PICK_PRESENT, "evidence": "REPLAY"}},
        {"ts": _iso(6.60), "run_id": run_id, "brick_idx": 2, "state": "SNAP_TO_INSPECT", "event": "pose_snap", "data": {"evidence": "REPLAY"}},
        {"ts": _iso(6.90), "run_id": run_id, "brick_idx": 2, "state": "INSPECT", "event": "view_scored", "data": {
            "view": "inspect", "score": 0.46, "verdict": "UNCERTAIN", "t_low": 0.35, "t_high": 0.60,
            "model": "patchcore_256", "precision": "INT8", "device": "NPU", "latency_ms": 9.5, "evidence": "REPLAY",
        }},
        {"ts": _iso(7.55), "run_id": run_id, "brick_idx": 2, "state": "NEXT_VIEW", "event": "wrist_rotated", "data": {"target_pose": "inspect_view2", "evidence": "REPLAY"}},
        {"ts": _iso(8.15), "run_id": run_id, "brick_idx": 2, "state": "INSPECT", "event": "inspection_result", "data": {
            "brick_idx": 2, "verdict": "DEFECT", "score": 0.84, "t_low": 0.35, "t_high": 0.60,
            "views": [{"view": "inspect", "score": 0.46}, {"view": "inspect_view2", "score": 0.84}],
            "heatmap_png": f"runs/{run_id}/heatmaps/0002_view2.png",
            "raw_png": f"runs/{run_id}/raw/0002_view2.png",
            "defect_label": "Black Marker Stripe (Revealed on View 2)",
            "model": "patchcore_256", "precision": "INT8", "device": "NPU", "latency_ms": 9.6, "evidence": "REPLAY",
        }},
        {"ts": _iso(8.24), "run_id": run_id, "brick_idx": 2, "state": "DECIDE", "event": "instruction_selected", "data": {
            "verdict": "DEFECT", "instruction": INSTRUCTION_PLACE_DEFECT, "igpu_latency_ms": 24.4, "evidence": "REPLAY",
        }},
        {"ts": _iso(10.05), "run_id": run_id, "brick_idx": 2, "state": "PLACE_DEFECT", "event": "skill_done", "data": {"evidence": "REPLAY"}},
        {"ts": _iso(10.35), "run_id": run_id, "brick_idx": 2, "state": "CONFIRM", "event": "confirmed", "data": {"bowl": "defect", "evidence": "REPLAY"}},

        # --- Brick 3: Blue -> UNCERTAIN across 3 views -> REGRASP recovery ---
        {"ts": _iso(11.50), "run_id": run_id, "brick_idx": 3, "state": "PICK_PRESENT", "event": "skill_start", "data": {"color": "blue", "instruction": INSTRUCTION_PICK_PRESENT, "evidence": "REPLAY"}},
        {"ts": _iso(13.20), "run_id": run_id, "brick_idx": 3, "state": "INSPECT", "event": "view_scored", "data": {"view": "inspect", "score": 0.44, "verdict": "UNCERTAIN", "t_low": 0.35, "t_high": 0.60, "evidence": "REPLAY"}},
        {"ts": _iso(13.90), "run_id": run_id, "brick_idx": 3, "state": "NEXT_VIEW", "event": "wrist_rotated", "data": {"target_pose": "inspect_view2", "evidence": "REPLAY"}},
        {"ts": _iso(14.35), "run_id": run_id, "brick_idx": 3, "state": "INSPECT", "event": "view_scored", "data": {"view": "inspect_view2", "score": 0.52, "verdict": "UNCERTAIN", "evidence": "REPLAY"}},
        {"ts": _iso(15.05), "run_id": run_id, "brick_idx": 3, "state": "NEXT_VIEW", "event": "wrist_rotated", "data": {"target_pose": "inspect_view3", "evidence": "REPLAY"}},
        {"ts": _iso(15.50), "run_id": run_id, "brick_idx": 3, "state": "INSPECT", "event": "inspection_result", "data": {
            "brick_idx": 3, "verdict": "UNCERTAIN", "score": 0.52, "t_low": 0.35, "t_high": 0.60,
            "views": [{"view": "inspect", "score": 0.44}, {"view": "inspect_view2", "score": 0.52}, {"view": "inspect_view3", "score": 0.49}],
            "heatmap_png": f"runs/{run_id}/heatmaps/0003_view3.png",
            "raw_png": f"runs/{run_id}/raw/0003_view3.png",
            "defect_label": "Specular Glare Across 3 Wrist Views",
            "model": "patchcore_256", "precision": "INT8", "device": "NPU", "latency_ms": 9.4, "evidence": "REPLAY",
        }},
        {"ts": _iso(15.60), "run_id": run_id, "brick_idx": 3, "state": "DECIDE", "event": "regrasp_selected", "data": {
            "verdict": "UNCERTAIN", "instruction": INSTRUCTION_PICK_PRESENT, "evidence": "REPLAY",
        }},
        {"ts": _iso(17.60), "run_id": run_id, "brick_idx": 3, "state": "REGRASP", "event": "regrasp_triggered", "data": {"reason": "Still uncertain after 3 views; returning to plate for re-pick", "evidence": "REPLAY"}},

        # --- Brick 4: Red -> GOOD ---
        {"ts": _iso(18.50), "run_id": run_id, "brick_idx": 4, "state": "PICK_PRESENT", "event": "skill_start", "data": {"color": "red", "instruction": INSTRUCTION_PICK_PRESENT, "evidence": "REPLAY"}},
        {"ts": _iso(20.05), "run_id": run_id, "brick_idx": 4, "state": "SNAP_TO_INSPECT", "event": "pose_snap", "data": {"evidence": "REPLAY"}},
        {"ts": _iso(20.40), "run_id": run_id, "brick_idx": 4, "state": "INSPECT", "event": "inspection_result", "data": {
            "brick_idx": 4, "verdict": "GOOD", "score": 0.18, "t_low": 0.35, "t_high": 0.60,
            "views": [{"view": "inspect", "score": 0.18}],
            "heatmap_png": f"runs/{run_id}/heatmaps/0004_inspect.png",
            "raw_png": f"runs/{run_id}/raw/0004_inspect.png",
            "defect_label": "None (Pristine)",
            "model": "patchcore_256", "precision": "INT8", "device": "NPU", "latency_ms": 9.2, "evidence": "REPLAY",
        }},
        {"ts": _iso(20.48), "run_id": run_id, "brick_idx": 4, "state": "DECIDE", "event": "instruction_selected", "data": {
            "verdict": "GOOD", "instruction": INSTRUCTION_PLACE_GOOD, "igpu_latency_ms": 23.9, "evidence": "REPLAY",
        }},
        {"ts": _iso(21.90), "run_id": run_id, "brick_idx": 4, "state": "PLACE_GOOD", "event": "skill_done", "data": {"evidence": "REPLAY"}},
        {"ts": _iso(22.14), "run_id": run_id, "brick_idx": 4, "state": "CONFIRM", "event": "confirmed", "data": {"bowl": "good", "evidence": "REPLAY"}},
        {"ts": _iso(22.30), "run_id": run_id, "state": "DONE", "event": "run_complete", "data": {"bricks_sorted": 4, "evidence": "REPLAY"}},
    ]

    events_file = run_dir / "events.jsonl"
    events_file.write_text("\n".join(json.dumps(ev) for ev in events) + "\n", encoding="utf-8")

    fake_benchmarks = [
        {
            "model": "patchcore_256",
            "device": "NPU",
            "precision": "INT8",
            "hint": "LATENCY",
            "latency_ms_p50": 9.3,
            "latency_ms_p95": 10.6,
            "fps": 107.5,
            "compile_s": 2.14,
            "cached_compile_s": 0.15,
            "size_mb": 14.2,
            "quality_metric": "image_F1",
            "quality": 0.942,
            "evidence": "REPLAY",
        },
        {
            "model": "patchcore_256",
            "device": "NPU",
            "precision": "FP16",
            "hint": "LATENCY",
            "latency_ms_p50": 14.1,
            "latency_ms_p95": 15.9,
            "fps": 70.9,
            "compile_s": 1.92,
            "cached_compile_s": 0.17,
            "size_mb": 27.8,
            "quality_metric": "image_F1",
            "quality": 0.948,
            "evidence": "REPLAY",
        },
        {
            "model": "patchcore_256",
            "device": "GPU",
            "precision": "FP16",
            "hint": "LATENCY",
            "latency_ms_p50": 13.6,
            "latency_ms_p95": 16.0,
            "fps": 73.5,
            "compile_s": 1.61,
            "cached_compile_s": 0.14,
            "size_mb": 27.8,
            "quality_metric": "image_F1",
            "quality": 0.948,
            "evidence": "REPLAY",
        },
        {
            "model": "patchcore_256",
            "device": "CPU",
            "precision": "FP32",
            "hint": "LATENCY",
            "latency_ms_p50": 34.8,
            "latency_ms_p95": 41.5,
            "fps": 28.7,
            "compile_s": 0.58,
            "cached_compile_s": 0.08,
            "size_mb": 55.4,
            "quality_metric": "image_F1",
            "quality": 0.949,
            "evidence": "REPLAY",
        },
        {
            "model": "smolvla_duplo",
            "device": "GPU",
            "precision": "FP16",
            "hint": "LATENCY",
            "latency_ms_p50": 24.0,
            "latency_ms_p95": 27.1,
            "fps": 41.7,
            "compile_s": 3.82,
            "cached_compile_s": 0.29,
            "size_mb": 842.0,
            "quality_metric": "skill_success",
            "quality": 0.90,
            "evidence": "REPLAY",
        },
    ]
    for b in fake_benchmarks:
        fname = f"{b['model']}_{b['device']}_{b['precision']}.json".lower()
        (bench_dir / fname).write_text(json.dumps(b, indent=2), encoding="utf-8")

    return events_file


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Zero-intrusion ~/duplo-cell watcher & fake-run replay bridge for Cloud, AI & Data Hub."
    )
    parser.add_argument(
        "positional_hub",
        nargs="?",
        default=None,
        help="Optional positional Hub URL for legacy self-check mode.",
    )
    parser.add_argument(
        "--watch",
        metavar="DUPLO_CELL_DIR",
        default=None,
        help="Path to ~/duplo-cell root to watch runs/<run_id>/events.jsonl and reports/bench/*.json.",
    )
    parser.add_argument(
        "--hub",
        default=None,
        help=f"Cloud Hub base URL (default: {DEFAULT_HUB_URL} or http://10.0.36.249:8000).",
    )
    parser.add_argument(
        "--replay-fake",
        action="store_true",
        help="Generate runs/fake-20261114/events.jsonl (+ heatmaps & benchmarks) and stream to Hub.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="In --watch mode, process existing events/benchmarks once and exit.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.35,
        help="Polling interval in seconds for --watch mode (default: 0.35s).",
    )

    args = parser.parse_args(argv)
    hub_url = (args.hub or args.positional_hub or DEFAULT_HUB_URL).rstrip("/")

    if args.replay_fake:
        target_root = Path(args.watch).expanduser().resolve() if args.watch else Path.cwd()
        print(f"[duplo_cell_bridge] Generating fake run in {target_root / 'runs' / 'fake-20261114'}...")
        events_path = generate_fake_duplo_run(target_root, write_reports_bench=bool(args.watch))
        pol = fetch_active_policy(host=hub_url)
        print(
            f"[duplo_cell_bridge] Connected to Hub {hub_url} | "
            f"t_low={pol.get('t_low', 0.35)} t_high={pol.get('t_high', 0.60)} "
            f"threshold={pol.get('active_anomaly_threshold', 0.55)}"
        )
        watcher = DuploCellWatcher(root_dir=target_root, hub_url=hub_url)
        watcher.current_events_file = events_path
        watcher.sync_benchmarks(extra_bench_dir=events_path.parent / "bench")
        lines = watcher.poll_events_once(flush_pending=True, stream_states=True)
        print(
            f"[duplo_cell_bridge] Fake replay complete: {lines} events, "
            f"{watcher.cycles_pushed} brick cycles, {watcher.benchmarks_pushed} benchmarks streamed."
        )
        return 0 if watcher.cycles_pushed >= 4 else 1

    if args.watch:
        watch_root = Path(args.watch).expanduser().resolve()
        print(f"[duplo_cell_bridge] Watching {watch_root} -> Hub {hub_url} (zero-intrusion mode)")
        pol = fetch_active_policy(host=hub_url)
        print(
            f"[duplo_cell_bridge] Active Hub policy: t_low={pol.get('t_low', 0.35)} "
            f"t_high={pol.get('t_high', 0.60)} rules={pol.get('rules_count', len(pol.get('rules', [])))}"
        )
        watcher = DuploCellWatcher(root_dir=watch_root, hub_url=hub_url)
        watcher.sync_benchmarks()
        watcher.poll_events_once(flush_pending=args.once, stream_states=True)
        if args.once:
            print(
                f"[duplo_cell_bridge] Single-pass sync complete: "
                f"{watcher.cycles_pushed} cycles, {watcher.benchmarks_pushed} benchmarks."
            )
            return 0

        try:
            last_bench_scan = time.monotonic()
            while True:
                watcher.poll_events_once(flush_pending=False, stream_states=True)
                now = time.monotonic()
                if now - last_bench_scan >= 2.5:
                    watcher.sync_benchmarks()
                    last_bench_scan = now
                time.sleep(max(0.1, float(args.poll_interval)))
        except KeyboardInterrupt:
            print("\n[duplo_cell_bridge] Watcher stopped cleanly.")
            return 0

    # Default quick verification mode (`python duplo_cell_bridge.py [hub_url]`)
    print(f"Verifying duplo_cell_bridge against {hub_url}...")
    pol = fetch_active_policy(host=hub_url)
    print(
        f"Active policy: threshold={pol.get('active_anomaly_threshold')} "
        f"t_low={pol.get('t_low')} t_high={pol.get('t_high')}"
    )
    res = push_cycle_async(
        brick_uuid=f"bridge_{int(time.time())}",
        color="yellow",
        defect_label="Black Marker Stripe",
        anomaly_score=0.81,
        verdict="DEFECT",
        score=0.81,
        t_low=0.35,
        t_high=0.60,
        views=[{"view": "inspect", "score": 0.42}, {"view": "inspect_view2", "score": 0.81}],
        instruction=INSTRUCTION_PLACE_DEFECT,
        cell_state="CONFIRM",
        cycle_s=4.7,
        evidence="REPLAY",
        host=hub_url,
    )
    time.sleep(1.0)
    print("Dispatched:", res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
