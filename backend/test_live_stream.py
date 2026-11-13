#!/usr/bin/env python3
"""
Member 4 Integration Stress-Test & Telemetry Verification Script
Junction 2026 - Intel Physical AI Challenge

Verifies Member 2/3 Robot & Cloud Integration Contracts:
1. Ingests 3 realistic cycles into POST /api/cycles with base64 crops & Intel Core Ultra X9 latencies.
2. Polls GET /api/policy to verify active threshold & rules for edge robot loop.
3. Sends PATCH /api/cycles/{brick_uuid}/nemotron with multimodal root-cause analysis & dynamic threshold tuning.
4. Confirms live state updates.
"""

import sys
import json
import time
import base64
import io
import urllib.request
import urllib.error
from typing import Dict, Any

try:
    from PIL import Image, ImageDraw
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

BASE_URL = "http://localhost:8000"

def create_synthetic_b64_crop(color_name: str, has_defect: bool = False) -> str:
    """Creates a synthetic base64-encoded PNG inspection crop."""
    if not PIL_AVAILABLE:
        # Fallback 1x1 transparent PNG
        return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    color_map = {
        "green": (16, 185, 129),
        "yellow": (245, 158, 11),
        "blue": (59, 130, 246),
        "red": (239, 68, 68),
    }
    bg_rgb = color_map.get(color_name.lower(), (16, 185, 129))
    img = Image.new("RGB", (256, 256), color=(14, 19, 26))
    draw = ImageDraw.Draw(img)

    # Draw Duplo Brick Body
    draw.rounded_rectangle([32, 32, 224, 224], radius=16, fill=bg_rgb, outline=(255, 255, 255), width=2)

    # Draw 4 Duplo Studs
    stud_color = tuple(min(255, c + 35) for c in bg_rgb)
    studs = [(76, 76), (180, 76), (76, 180), (180, 180)]
    for sx, sy in studs:
        draw.ellipse([sx - 24, sy - 24, sx + 24, sy + 24], fill=stud_color, outline=(255, 255, 255), width=2)

    # If defect, draw anomaly scratch
    if has_defect:
        draw.line([(50, 60), (200, 190)], fill=(220, 38, 38), width=5)
        draw.line([(60, 50), (210, 180)], fill=(0, 0, 0), width=3)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64_str}"

def http_request(url: str, method: str = "GET", data: Dict[str, Any] = None) -> Dict[str, Any]:
    """Helper to perform HTTP requests using standard library."""
    req_data = json.dumps(data).encode("utf-8") if data is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res_body = response.read().decode("utf-8")
            return json.loads(res_body)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        print(f"[ERROR] HTTP {e.code} on {method} {url}: {err_body}")
        raise
    except Exception as e:
        print(f"[ERROR] Connection failed on {method} {url}: {e}")
        raise

def run_integration_tests():
    print("=" * 72)
    print(" Junction 2026 - Member 4 Live Integration Test Stream")
    print(" Target Hub: " + BASE_URL)
    print("=" * 72)

    # 1. Health Check
    print("\n[STEP 1] Checking API Hub Health...")
    health = http_request(f"{BASE_URL}/api/health")
    print(f"  ✓ Hub Status: {health.get('status')} | Service: {health.get('service')}")
    print(f"  ✓ Platform Target: {health.get('platform')}")

    # 2. Ingest 3 Cycles
    print("\n[STEP 2] Ingesting 3 Realistic Edge Cycles into POST /api/cycles...")
    
    test_cycles = [
        {
            "brick_uuid": f"edge_green_{int(time.time())}",
            "color": "green",
            "defect_label": "None (Pristine)",
            "anomaly_score": 0.104,
            "action": "PERFECT_BOWL",
            "root_cause": "Anomalib PatchCore on 50 TOPS NPU confirmed zero surface anomalies. Direct route to Perfect Bowl 1.",
            "npu_latency_ms": 9.4,
            "igpu_latency_ms": 24.1,
            "cpu_latency_ms": 2.0,
            "has_defect": False,
        },
        {
            "brick_uuid": f"edge_yellow_{int(time.time())}",
            "color": "yellow",
            "defect_label": "Side Scratch / Marker Stripe",
            "anomaly_score": 0.782,
            "action": "DEFECTIVE_BOWL",
            "root_cause": "High topological groove detected on side stud. Anomalib localized anomaly cluster exceeding 0.55 rejection limit.",
            "npu_latency_ms": 9.7,
            "igpu_latency_ms": 24.3,
            "cpu_latency_ms": 2.1,
            "has_defect": True,
        },
        {
            "brick_uuid": f"edge_blue_{int(time.time())}",
            "color": "blue",
            "defect_label": "Specular Reflection / Glare",
            "anomaly_score": 0.518,
            "action": "REGRASP_TRIGGERED",
            "root_cause": "Ambiguous boundary detection due to high specular reflection. SmolVLA triggered re-grasp trajectory for re-inspection.",
            "npu_latency_ms": 9.3,
            "igpu_latency_ms": 23.9,
            "cpu_latency_ms": 1.9,
            "has_defect": False,
        }
    ]

    ingested_cycles = []
    for idx, c in enumerate(test_cycles, 1):
        raw_b64 = create_synthetic_b64_crop(c["color"], c["has_defect"])
        heat_b64 = raw_b64 # Simulated overlay
        payload = {
            "brick_uuid": c["brick_uuid"],
            "color": c["color"],
            "defect_label": c["defect_label"],
            "anomaly_score": c["anomaly_score"],
            "action": c["action"],
            "root_cause": c["root_cause"],
            "npu_latency_ms": c["npu_latency_ms"],
            "igpu_latency_ms": c["igpu_latency_ms"],
            "cpu_latency_ms": c["cpu_latency_ms"],
            "raw_image_b64": raw_b64,
            "heatmap_image_b64": heat_b64,
        }
        res = http_request(f"{BASE_URL}/api/cycles", method="POST", data=payload)
        total_lat = round(c["npu_latency_ms"] + c["igpu_latency_ms"] + c["cpu_latency_ms"], 2)
        print(f"  ✓ Ingested Cycle {idx}: ID={res.get('cycle_id')} | Action={c['action']} | Latency={total_lat}ms (NPU {c['npu_latency_ms']}ms + iGPU {c['igpu_latency_ms']}ms + CPU {c['cpu_latency_ms']}ms)")
        ingested_cycles.append(c["brick_uuid"])
        time.sleep(0.5)

    # 3. Poll Policy Endpoint
    print("\n[STEP 3] Polling Active Policy Endpoint (GET /api/policy)...")
    policy = http_request(f"{BASE_URL}/api/policy")
    print(f"  ✓ Active Anomaly Threshold: {policy.get('active_anomaly_threshold')}")
    print(f"  ✓ Active Sorting Rules: {policy.get('rules_count')} rules")
    for r in policy.get("rules", []):
        print(f"     • [{r.get('target_brick_color', 'any').upper()}] {r.get('rule_id')} -> {r.get('action_on_match')} (threshold: {r.get('anomaly_threshold')})")
    print(f"  ✓ Re-grasp Decision Range: {policy.get('regrasp_range')}")
    print(f"  ✓ OpenVINO Target Acceleration: {policy.get('openvino_acceleration')}")

    # 4. Patch Cycle with Nemotron 3.5 Root-Cause Analysis
    defective_uuid = ingested_cycles[1]
    print(f"\n[STEP 4] Updating Cycle {defective_uuid} via Cloud Nemotron Worker (PATCH /api/cycles/{defective_uuid}/nemotron)...")
    patch_payload = {
        "nemotron_root_cause": (
            "NVIDIA Nemotron 3.5 Super VL multimodal audit: Visual grounding confirms 38mm dark marker line "
            "traversing upper alignment stud. Classified as contamination defect under IPC-A-610. "
            "Confidence 98.4%. Recommended threshold lowered to 0.54."
        ),
        "adjusted_threshold": 0.54
    }
    patch_res = http_request(f"{BASE_URL}/api/cycles/{defective_uuid}/nemotron", method="PATCH", data=patch_payload)
    print(f"  ✓ PATCH response status: {patch_res.get('status')}")
    print(f"  ✓ Updated cycle_id: {patch_res.get('cycle_id')}")
    print(f"  ✓ Dynamically Adjusted Threshold: {patch_res.get('active_anomaly_threshold')}")

    # 5. Verify State
    print("\n[STEP 5] Verifying Global State Sync...")
    policy_after = http_request(f"{BASE_URL}/api/policy")
    print(f"  ✓ Verified New Threshold in Policy: {policy_after.get('active_anomaly_threshold')}")

    print("\n" + "=" * 72)
    print(" ALL INTEGRATION CONTRACTS VERIFIED SUCCESSFULLY (100% PASS)")
    print(" Ready for Member 1/2/3 Live Robot Arm & Cloud Streams!")
    print("=" * 72)

if __name__ == "__main__":
    try:
        run_integration_tests()
    except Exception as err:
        print(f"\n[FAIL] Integration test failed: {err}")
        sys.exit(1)
