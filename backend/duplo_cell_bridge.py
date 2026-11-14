#!/usr/bin/env python3
"""
duplo_cell_bridge.py
Zero-dependency drop-in bridge for ~/duplo-cell to stream cycles to the Unified Cloud & AI Hub.
Provides `push_cycle_async`, `send_cycle_to_dashboard`, `get_active_policy`, and `patch_nemotron_analysis`
using only Python's standard library (`urllib.request`, `json`, `threading`).
"""

from duplo_bridge_example import (
    DEFAULT_HUB_URL,
    get_active_policy,
    send_cycle_to_dashboard,
    patch_nemotron_analysis,
)


def push_cycle_async(
    brick_uuid: str | None = None,
    color: str = "blue",
    defect_label: str = "Pristine",
    anomaly_score: float = 0.12,
    action: str = "PERFECT_BOWL",
    root_cause: str | None = None,
    npu_latency_ms: float = 9.4,
    igpu_latency_ms: float = 24.1,
    cpu_latency_ms: float = 2.1,
    raw_image_b64: str | None = None,
    heatmap_image_b64: str | None = None,
    host: str = DEFAULT_HUB_URL,
):
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
    )


if __name__ == "__main__":
    import sys
    import time

    hub = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HUB_URL
    print(f"Verifying duplo_cell_bridge against {hub}...")
    pol = get_active_policy(host=hub)
    print("Active policy threshold:", pol.get("active_anomaly_threshold"))
    res = push_cycle_async(
        brick_uuid=f"bridge_{int(time.time())}",
        color="yellow",
        defect_label="Black Marker Stripe",
        anomaly_score=0.81,
        action="DEFECTIVE_BOWL",
        host=hub,
    )
    time.sleep(1.0)
    print("Dispatched:", res)
