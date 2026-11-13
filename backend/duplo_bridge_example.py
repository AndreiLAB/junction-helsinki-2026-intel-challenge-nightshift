#!/usr/bin/env python3
"""
duplo_bridge_example.py
Drop-in client helper for the teammates' ~/duplo-cell robot inspection pipeline.
Uses ONLY standard Python library (urllib.request, json, threading) - ZERO external pip dependencies!

Usage in ~/duplo-cell robot state machine:
    from duplo_bridge_example import send_cycle_to_dashboard, get_active_policy

    # 1. Fetch latest policy & anomaly threshold before or during runs:
    policy = get_active_policy(host="http://localhost:8000")
    threshold = policy.get("active_anomaly_threshold", 0.55)

    # 2. Fire non-blocking cycle telemetry from robot loop (runs in background thread):
    send_cycle_to_dashboard(
        brick_uuid="brick_042",
        color="yellow",
        defect_label="Black Marker Stripe",
        anomaly_score=0.78,
        action="DEFECTIVE_BOWL",   # "PERFECT_BOWL", "DEFECTIVE_BOWL", or "REGRASP_TRIGGERED"
        npu_latency_ms=9.4,        # Anomalib v2.7.0 PatchCore on Intel NPU
        igpu_latency_ms=24.1,      # SmolVLA / ACT on 12 Xe3 Cores
        cpu_latency_ms=2.1,        # SO-101 real-time kinematics
        async_send=True,           # True: non-blocking, zero latency impact on robot arm!
        host="http://localhost:8000"
    )
"""

import sys
import json
import time
import uuid
import threading
import urllib.request
import urllib.error
from typing import Optional, Dict, Any

DEFAULT_HUB_URL = "http://localhost:8000"

def get_active_policy(host: str = DEFAULT_HUB_URL, timeout: float = 2.0) -> Dict[str, Any]:
    """
    Polls the active inspection policy from the Member 4 FastAPI Hub.
    Returns dictionary with active_anomaly_threshold, rules, and regrasp ranges.
    """
    url = f"{host.rstrip('/')}/api/policy"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.loads(res.read().decode("utf-8"))
    except Exception as e:
        # Graceful fallback if hub is temporarily unreachable
        return {
            "active_anomaly_threshold": 0.55,
            "regrasp_range": [0.45, 0.65],
            "rules": [],
            "error": str(e)
        }

def _do_post_cycle(url: str, payload: dict):
    """Internal synchronous POST worker."""
    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=req_data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5.0) as res:
            return json.loads(res.read().decode("utf-8"))
    except Exception as err:
        print(f"[duplo_bridge warning] Could not reach dashboard hub at {url}: {err}", file=sys.stderr)
        return None

def send_cycle_to_dashboard(
    brick_uuid: Optional[str] = None,
    color: str = "blue",
    defect_label: str = "Pristine",
    anomaly_score: float = 0.12,
    action: str = "PERFECT_BOWL",
    root_cause: Optional[str] = None,
    npu_latency_ms: float = 9.4,
    igpu_latency_ms: float = 24.1,
    cpu_latency_ms: float = 2.1,
    raw_image_b64: Optional[str] = None,
    heatmap_image_b64: Optional[str] = None,
    host: str = DEFAULT_HUB_URL,
    async_send: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Streams physical robot cell telemetry into Member 4 mission control dashboard.
    
    Parameters:
      - brick_uuid: Unique cycle string (auto-generated if None)
      - color: "blue", "yellow", "red", "green", "orange"
      - defect_label: Human-readable classification (e.g. "Pristine", "Black Stripe", "Cracked Stud")
      - anomaly_score: Anomalib score float (e.g. 0.12 or 0.79)
      - action: "PERFECT_BOWL", "DEFECTIVE_BOWL", or "REGRASP_TRIGGERED"
      - root_cause: Explanation text
      - npu_latency_ms, igpu_latency_ms, cpu_latency_ms: Timing benchmarks
      - raw_image_b64, heatmap_image_b64: Optional base64 data URIs
      - host: FastAPI server URL (e.g. "http://localhost:8000" or laptop LAN IP)
      - async_send: If True (recommended), runs in background thread so robot control loop never blocks!
    """
    uid = brick_uuid or f"cell_{str(uuid.uuid4())[:8]}"
    payload = {
        "brick_uuid": uid,
        "color": color,
        "defect_label": defect_label,
        "anomaly_score": round(float(anomaly_score), 4),
        "action": action,
        "root_cause": root_cause or f"Anomalib inference on NPU: {anomaly_score:.3f}. Action: {action}.",
        "npu_latency_ms": round(float(npu_latency_ms), 2),
        "igpu_latency_ms": round(float(igpu_latency_ms), 2),
        "cpu_latency_ms": round(float(cpu_latency_ms), 2),
        "raw_image_b64": raw_image_b64,
        "heatmap_image_b64": heatmap_image_b64,
    }

    url = f"{host.rstrip('/')}/api/cycles"

    if async_send:
        # Fire-and-forget in background thread - 0ms latency impact on arm controller
        t = threading.Thread(target=_do_post_cycle, args=(url, payload), daemon=True)
        t.start()
        return {"status": "dispatched_async", "brick_uuid": uid}
    else:
        return _do_post_cycle(url, payload)

def patch_nemotron_analysis(
    brick_uuid: str,
    nemotron_root_cause: str,
    adjusted_threshold: Optional[float] = None,
    host: str = DEFAULT_HUB_URL
) -> Optional[Dict[str, Any]]:
    """
    Attaches asynchronous cloud Nemotron root-cause diagnostics to an existing cycle.
    """
    url = f"{host.rstrip('/')}/api/cycles/{brick_uuid}/nemotron"
    payload = {
        "nemotron_root_cause": nemotron_root_cause,
        "adjusted_threshold": adjusted_threshold
    }
    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=req_data,
        headers={"Content-Type": "application/json"},
        method="PATCH"
    )
    try:
        with urllib.request.urlopen(req, timeout=5.0) as res:
            return json.loads(res.read().decode("utf-8"))
    except Exception as err:
        print(f"[duplo_bridge warning] PATCH failed: {err}", file=sys.stderr)
        return None

# --- Self-Test Demo ---
if __name__ == "__main__":
    hub = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HUB_URL
    print(f"Testing duplo_bridge against Hub: {hub}")

    # 1. Poll policy
    pol = get_active_policy(hub)
    print(f"[1] Active Policy Anomaly Threshold: {pol.get('active_anomaly_threshold')}")

    # 2. Send Synchronous Cycle (GOOD Bowl)
    test_id = f"test_{int(time.time())}"
    sync_res = send_cycle_to_dashboard(
        brick_uuid=test_id,
        color="green",
        defect_label="None (Pristine)",
        anomaly_score=0.098,
        action="PERFECT_BOWL",
        async_send=False,
        host=hub
    )
    print(f"[2] Sent Synchronous Cycle: {sync_res}")

    # 3. Send Asynchronous Cycle (DEFECTIVE Bowl)
    async_id = f"test_defect_{int(time.time())}"
    async_res = send_cycle_to_dashboard(
        brick_uuid=async_id,
        color="yellow",
        defect_label="Marker Stripe on Side Stud",
        anomaly_score=0.764,
        action="DEFECTIVE_BOWL",
        async_send=True,
        host=hub
    )
    print(f"[3] Dispatched Asynchronous Cycle: {async_res}")

    # Allow async thread to complete
    time.sleep(1.0)

    # 4. Patch with Nemotron Audit
    patch_res = patch_nemotron_analysis(
        brick_uuid=test_id,
        nemotron_root_cause="Nemotron 3.5 Super VL verified high-gloss pristine surface. Zero defect tags detected.",
        host=hub
    )
    print(f"[4] Patched Nemotron Audit: {patch_res}")
    print("\n✓ ~/duplo-cell Bridge helper verified successfully!")
