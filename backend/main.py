import os
import uuid
import time
import random
import asyncio
import logging
from typing import List, Dict, Any, Optional, Union
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import cloudinary_media
from cloudinary_media import upload_inspection_with_heatmap, create_simulated_brick_image
from gemini_copilot import extract_rule_from_multimodal, SortingRule, GEMINI_MODEL
from mariadb_store import (
    compute_brick_embedding,
    record_cycle_and_find_similar,
    find_similar_for_cycle_id,
    record_policy_change,
    get_policy_history,
    record_benchmarks,
    get_benchmarks,
    get_mariadb_status,
)
from nemotron_worker import analyze_cycle_with_nemotron, get_nemotron_status
from modal_webhook import (
    dispatch_modal_escalation,
    evaluate_escalation_payload,
    get_modal_status,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("junction_backend")

# Exact ~/duplo-cell Shared Contracts (docs/CONTRACTS.md & configs/station.yaml)
INSTRUCTION_PICK_PRESENT = "Pick up a brick and hold it in front of the inspection camera."
INSTRUCTION_PLACE_GOOD = "Put the brick in the good bowl."
INSTRUCTION_PLACE_DEFECT = "Put the brick in the defective bowl."

VALID_CELL_STATES = (
    "HOME",
    "PICK_PRESENT",
    "SNAP_TO_INSPECT",
    "CHECK_HELD",
    "INSPECT",
    "DECIDE",
    "PLACE_GOOD",
    "PLACE_DEFECT",
    "NEXT_VIEW",
    "REGRASP",
    "CONFIRM",
    "DONE",
    "FAULT",
)


def map_cell_state_to_pipeline_stage(cell_state: Optional[str]) -> str:
    st = (cell_state or "").strip().upper()
    if st in ("PICK_PRESENT", "SNAP_TO_INSPECT", "CHECK_HELD"):
        return "PERCEIVE"
    if st in ("INSPECT", "NEXT_VIEW"):
        return "DETECT"
    if st == "DECIDE":
        return "REASON"
    if st in ("PLACE_GOOD", "PLACE_DEFECT", "REGRASP", "CONFIRM", "FAULT"):
        return "ACT"
    if st == "DONE":
        return "OPTIMIZE"
    return "IDLE"


def resolve_verdict_and_action(
    verdict: Optional[str],
    action: Optional[str],
    score: float,
    t_low: float,
    t_high: float,
) -> tuple[str, str]:
    """
    Bidirectionally maps ~/duplo-cell `verdict` <-> Hub `action`:
      GOOD      <-> PERFECT_BOWL
      DEFECT    <-> DEFECTIVE_BOWL
      UNCERTAIN -> REGRASP_TRIGGERED
      NO_BRICK  -> REGRASP_TRIGGERED
    """
    v_clean = (verdict or "").strip().upper()
    a_clean = (action or "").strip().upper()

    if v_clean in ("GOOD", "DEFECT", "UNCERTAIN", "NO_BRICK"):
        if not a_clean:
            if v_clean == "GOOD":
                a_clean = "PERFECT_BOWL"
            elif v_clean == "DEFECT":
                a_clean = "DEFECTIVE_BOWL"
            else:
                a_clean = "REGRASP_TRIGGERED"
        return v_clean, a_clean

    if a_clean:
        if a_clean == "PERFECT_BOWL":
            return "GOOD", "PERFECT_BOWL"
        if a_clean == "DEFECTIVE_BOWL":
            return "DEFECT", "DEFECTIVE_BOWL"
        return "UNCERTAIN", "REGRASP_TRIGGERED"

    if score < t_low:
        return "GOOD", "PERFECT_BOWL"
    if score > t_high:
        return "DEFECT", "DEFECTIVE_BOWL"
    return "UNCERTAIN", "REGRASP_TRIGGERED"


def resolve_vla_instruction(instruction: Optional[str], verdict: str, action: str) -> str:
    if instruction and instruction.strip():
        return instruction.strip()
    if verdict == "GOOD" or action == "PERFECT_BOWL":
        return INSTRUCTION_PLACE_GOOD
    if verdict == "DEFECT" or action == "DEFECTIVE_BOWL":
        return INSTRUCTION_PLACE_DEFECT
    return INSTRUCTION_PICK_PRESENT


def normalize_image_uri(img_data: Optional[str]) -> Optional[str]:
    if not img_data or not isinstance(img_data, str):
        return None
    s = img_data.strip()
    if not s:
        return None
    if s.startswith(("data:image/", "http://", "https://", "sim_", "raw_", "init_", "heat_")):
        return s
    if os.path.isfile(s):
        return s
    if len(s) >= 64 and " " not in s:
        return f"data:image/png;base64,{s}"
    return s


# Connection Manager for WebSockets
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Remaining: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Error broadcasting to client: {e}")
                self.disconnect(connection)

manager = ConnectionManager()

# In-memory State Store
class SystemState:
    def __init__(self):
        self.active_rules: List[SortingRule] = [
            SortingRule(
                rule_id="baseline_reject_cracked_studs",
                target_brick_color="any",
                defect_description="Cracked, split, or deformed top studs",
                anomaly_threshold=0.55,
                action_on_match="DEFECTIVE_BOWL",
                spoken_confirmation="Baseline rule active: Rejecting any brick with cracked or split top studs into the defective bowl.",
                reasoning="Physical structural defect prevents interlocking; immediate discard.",
                created_at="Kickoff",
                active=True,
            ),
            SortingRule(
                rule_id="reject_yellow_black_stripes",
                target_brick_color="yellow",
                defect_description="Black side stripes or marker lines",
                anomaly_threshold=0.50,
                action_on_match="DEFECTIVE_BOWL",
                spoken_confirmation="Rule active: Rejecting yellow bricks with black side stripes into the defective bowl.",
                reasoning="Contamination / operator marked test coupon.",
                created_at="Kickoff",
                active=True,
            ),
            SortingRule(
                rule_id="regrasp_blue_glare",
                target_brick_color="blue",
                defect_description="Specular glare causing ambiguous edge detection",
                anomaly_threshold=0.48,
                action_on_match="REGRASP_AND_RECHECK",
                spoken_confirmation="Rule active: Re-grasping blue bricks when high specular reflection causes boundary uncertainty.",
                reasoning="Wrist camera re-orientation to resolve specular highlights.",
                created_at="Kickoff",
                active=True,
            )
        ]
        self.active_anomaly_threshold: float = 0.55
        self.t_low: float = 0.35
        self.t_high: float = 0.60
        self.recent_cycles: List[Dict[str, Any]] = []
        self.benchmarks: List[Dict[str, Any]] = []
        self.current_pipeline_stage: str = "IDLE" # IDLE, PERCEIVE, DETECT, REASON, ACT, OPTIMIZE
        self.current_cell_state: str = "HOME"     # ~/duplo-cell state machine state
        self.simulation_running: bool = False
        self.simulation_task: Optional[asyncio.Task] = None
        self.background_tasks: set[asyncio.Task] = set()

        # Telemetry metrics for Intel Core Ultra X9 388H AI PC
        self.hardware_metrics = {
            "platform": "Intel® Core™ Ultra X9 Series 3 (388H) AI PC",
            "total_tops": 180,
            "npu": {
                "name": "Intel NPU 50 TOPS",
                "workload": "Anomalib v2.7.0 (PatchCore / EfficientNet)",
                "latency_ms": 9.4,
                "utilization_pct": 74.2,
                "power_watts": 4.8,
                "efficiency": "88% perf/watt",
            },
            "igpu": {
                "name": "Intel 12 Xe3 Cores iGPU",
                "workload": "SmolVLA / ACT Policy (Physical AI Studio)",
                "latency_ms": 24.1,
                "utilization_pct": 68.5,
                "throughput_fps": 41.5,
                "precision": "FP16 / oneAPI",
            },
            "cpu": {
                "name": "Intel Core Ultra (Deterministic Control)",
                "workload": "Real-time Kinematics & TCC+TSN loop",
                "latency_ms": 2.1,
                "utilization_pct": 28.0,
                "jitter_us": 12.4,
                "temp_c": 52,
            },
            "total_pipeline_latency_ms": 35.6,
            "avg_cycle_s": 4.1,
            "latest_cycle_s": 3.9,
            "total_cycles_processed": 0,
            "perfect_count": 0,
            "defective_count": 0,
            "regrasp_count": 0,
        }

state = SystemState()


class ViewScoreItem(BaseModel):
    view: str = "inspect"
    score: float


# Pydantic models for incoming telemetry (backward-compatible + native ~/duplo-cell contracts)
class CycleIngestRequest(BaseModel):
    brick_uuid: Optional[str] = None
    color: Optional[str] = "blue"
    defect_label: Optional[str] = None
    anomaly_score: Optional[float] = None
    action: Optional[str] = None
    root_cause: Optional[str] = None
    npu_latency_ms: Optional[float] = None
    igpu_latency_ms: Optional[float] = None
    cpu_latency_ms: Optional[float] = None
    raw_image_b64: Optional[str] = None
    heatmap_image_b64: Optional[str] = None
    top_image_b64: Optional[str] = None

    # Native ~/duplo-cell InspectionResult & events.jsonl contract fields
    brick_idx: Optional[int] = None
    run_id: Optional[str] = None
    ts: Optional[str] = None
    verdict: Optional[str] = None
    score: Optional[float] = None
    t_low: Optional[float] = None
    t_high: Optional[float] = None
    views: Optional[List[ViewScoreItem]] = None
    heatmap_png: Optional[str] = None
    instruction: Optional[str] = None
    cell_state: Optional[str] = None
    model: Optional[str] = None
    precision: Optional[str] = None
    device: Optional[str] = None
    latency_ms: Optional[float] = None
    cycle_s: Optional[float] = None
    stage_durations_s: Optional[Dict[str, float]] = None
    evidence: Optional[str] = None


class BenchmarkRecord(BaseModel):
    model: str
    device: str
    precision: str
    hint: Optional[str] = "LATENCY"
    latency_ms_p50: float = 0.0
    latency_ms_p95: float = 0.0
    fps: float = 0.0
    compile_s: float = 0.0
    cached_compile_s: Optional[float] = 0.0
    size_mb: float = 0.0
    quality_metric: Optional[str] = "image_F1"
    quality: float = 0.0
    evidence: Optional[str] = "MOCK"
    notes: Optional[str] = None


class CellStateEventRequest(BaseModel):
    run_id: Optional[str] = None
    brick_idx: Optional[int] = None
    cell_state: str
    event: Optional[str] = None
    instruction: Optional[str] = None
    verdict: Optional[str] = None
    score: Optional[float] = None
    evidence: Optional[str] = None


class NemotronUpdateRequest(BaseModel):
    nemotron_root_cause: str
    adjusted_threshold: Optional[float] = None


def get_cloud_providers_status() -> Dict[str, Any]:
    gem_key = os.environ.get("GEMINI_API_KEY", "").strip()
    gem_live = bool(gem_key and gem_key != "your_gemini_key_here" and len(gem_key) >= 15)
    cld_live = bool(cloudinary_media.cloudinary_enabled)
    return {
        "gemini": {
            "configured": gem_live,
            "live": gem_live,
            "mode": "LIVE" if gem_live else "FALLBACK",
            "detail": f"{GEMINI_MODEL} structured copilot" if gem_live else "Heuristic copilot fallback",
        },
        "cloudinary": {
            "configured": cld_live,
            "live": cld_live,
            "mode": "LIVE" if cld_live else "FALLBACK",
            "detail": "Cloudinary l_overlay active" if cld_live else "Local 512px PNG synthesizer",
        },
        "nemotron": get_nemotron_status(),
        "mariadb": get_mariadb_status(),
        "modal": get_modal_status(),
    }


def _spawn_background_enrichment(cycle_record: Dict[str, Any]) -> None:
    cid = str(cycle_record.get("cycle_id", ""))
    if cid.startswith("CYC-init_") or cid.startswith("init_"):
        return
    task = asyncio.create_task(_background_cloud_enrichment(cycle_record))
    state.background_tasks.add(task)
    task.add_done_callback(state.background_tasks.discard)


async def _background_cloud_enrichment(cycle_record: Dict[str, Any]) -> None:
    """
    Runs off the critical robot loop path (0 ms added latency):
    1. Queries Verda B300 NVIDIA Nemotron 3.5 Super VL for visual root-cause & threshold tuning.
    2. Dispatches Modal serverless escalation webhook on DEFECTIVE_BOWL / REGRASP_TRIGGERED.
    3. Broadcasts CYCLE_UPDATED over /ws/live.
    """
    cid = str(cycle_record.get("cycle_id", ""))
    if cid.startswith("CYC-init_") or cid.startswith("init_"):
        return

    action = cycle_record.get("action", "")
    needs_modal = action in ("DEFECTIVE_BOWL", "REGRASP_TRIGGERED", "REGRASP_AND_RECHECK")

    if needs_modal:
        try:
            modal_res = await dispatch_modal_escalation(cycle_record)
            if isinstance(modal_res, dict):
                cycle_record["modal_escalation"] = modal_res
                await manager.broadcast({
                    "type": "CYCLE_UPDATED",
                    "cycle": cycle_record,
                    "active_anomaly_threshold": state.active_anomaly_threshold,
                    "cloud_providers": get_cloud_providers_status(),
                })
        except Exception as exc:
            logger.warning("Modal background escalation error: %s", type(exc).__name__)

    nem_res = await analyze_cycle_with_nemotron(cycle_record)
    if isinstance(nem_res, dict):
        if not cycle_record.get("nemotron_manual_patch"):
            root_cause = nem_res.get("root_cause")
            if root_cause:
                cycle_record["nemotron_reasoning"] = root_cause
                cycle_record["root_cause_reasoning"] = root_cause
            cycle_record["nemotron_provider"] = nem_res.get("provider", "fallback")

        suggested = nem_res.get("suggested_threshold")
        if suggested is not None and nem_res.get("provider") == "verda_b300":
            state.active_anomaly_threshold = float(suggested)
            logger.info("Verda B300 Nemotron auto-tuned threshold to %s", suggested)
            await record_policy_change(
                policy_id="global_anomaly_threshold",
                source="verda_b300_nemotron",
                event_type="THRESHOLD_TUNED",
                anomaly_threshold=state.active_anomaly_threshold,
                active_global_threshold=state.active_anomaly_threshold,
                target_brick_color=str(cycle_record.get("color", "any")),
                defect_description=str(cycle_record.get("defect_label", "")),
                action_on_match=str(cycle_record.get("action", "DEFECTIVE_BOWL")),
                is_active=True,
                reasoning=str(cycle_record.get("nemotron_reasoning", "")),
            )

    await manager.broadcast({
        "type": "CYCLE_UPDATED",
        "cycle": cycle_record,
        "active_anomaly_threshold": state.active_anomaly_threshold,
        "cloud_providers": get_cloud_providers_status(),
    })

# Background continuous simulation loop
async def continuous_simulator_loop():
    logger.info("Continuous cycle simulator background loop started.")
    cycle_templates = ["PERFECT", "DEFECTIVE", "REGRASP", "PERFECT", "DEFECTIVE"]
    template_idx = 0

    while state.simulation_running:
        try:
            chosen = cycle_templates[template_idx % len(cycle_templates)]
            template_idx += 1
            await execute_full_cycle_simulation(chosen)
            await asyncio.sleep(6.0)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in continuous simulator loop: {e}")
            await asyncio.sleep(5.0)

async def set_stage(stage: str, cell_state: Optional[str] = None):
    state.current_pipeline_stage = stage
    if cell_state:
        state.current_cell_state = cell_state
    await manager.broadcast({
        "type": "STAGE_CHANGE",
        "stage": stage,
        "cell_state": state.current_cell_state,
        "timestamp": time.time(),
    })


def _recompute_cycle_s_metrics() -> None:
    durations = [
        float(c["cycle_s"])
        for c in state.recent_cycles
        if c.get("cycle_s") is not None and float(c.get("cycle_s") or 0.0) > 0.0
    ]
    if durations:
        state.hardware_metrics["latest_cycle_s"] = round(durations[0], 2)
        state.hardware_metrics["avg_cycle_s"] = round(sum(durations) / len(durations), 2)


async def execute_full_cycle_simulation(outcome_type: Optional[str] = None):
    """
    Executes a high-fidelity physical AI cycle stepping through:
    PERCEIVE -> DETECT -> REASON -> ACT -> OPTIMIZE -> IDLE
    """
    brick_uuid = str(uuid.uuid4())[:8]
    brick_idx = state.hardware_metrics["total_cycles_processed"] + 1
    colors = ["blue", "yellow", "red", "green", "orange"]
    chosen_color = random.choice(colors)

    if outcome_type is None:
        outcome_type = random.choice(["PERFECT", "DEFECTIVE", "REGRASP"])
    else:
        outcome_upper = outcome_type.upper()
        if "PERFECT" in outcome_upper or "GOOD" in outcome_upper or "ACCEPT" in outcome_upper:
            outcome_type = "PERFECT"
        elif "DEFECT" in outcome_upper or "REJECT" in outcome_upper:
            outcome_type = "DEFECTIVE"
        else:
            outcome_type = "REGRASP"

    # 1. PERCEIVE: Camera frame acquisition
    await set_stage("PERCEIVE", "PICK_PRESENT")
    await asyncio.sleep(0.35)

    # 2. DETECT: Anomalib v2.7.0 on 50 TOPS NPU
    await set_stage("DETECT", "INSPECT")
    npu_lat = round(random.uniform(8.9, 9.8), 2)
    state.hardware_metrics["npu"]["latency_ms"] = npu_lat
    await asyncio.sleep(0.4)

    t_low = state.t_low
    t_high = state.t_high

    if outcome_type == "PERFECT":
        score = round(random.uniform(0.08, 0.24), 3)
        verdict = "GOOD"
        defect_label = "None (Pristine)"
        action = "PERFECT_BOWL"
        instruction = INSTRUCTION_PLACE_GOOD
        final_cell_state = "CONFIRM"
        cycle_s = round(random.uniform(3.4, 4.1), 2)
        views = [{"view": "inspect", "score": score}]
        reasoning = (
            f"Anomalib PatchCore on 50 TOPS NPU detected zero topological variance (score: {score:.2f} < t_low {t_low:.2f}). "
            f"Core Ultra Xe3 VLA executed \"{instruction}\"."
        )
        state.hardware_metrics["perfect_count"] += 1
    elif outcome_type == "DEFECTIVE":
        v1_score = round(random.uniform(0.41, 0.56), 3)
        score = round(random.uniform(0.68, 0.92), 3)
        verdict = "DEFECT"
        defect_label = random.choice([
            "Side Scratch / Deep Groove",
            "Cracked Stud Alignment",
            "Marker Stripe Contamination",
            "Chipped Corner Flaw"
        ])
        action = "DEFECTIVE_BOWL"
        instruction = INSTRUCTION_PLACE_DEFECT
        final_cell_state = "CONFIRM"
        cycle_s = round(random.uniform(4.5, 5.4), 2)
        views = [
            {"view": "inspect", "score": v1_score},
            {"view": "inspect_view2", "score": score},
        ]
        reasoning = (
            f"Multi-view wrist inspection localized anomaly cluster (max score: {score:.2f} > t_high {t_high:.2f}). "
            f"SmolVLA task policy executed \"{instruction}\"."
        )
        state.hardware_metrics["defective_count"] += 1
    else: # REGRASP / UNCERTAIN
        v1_score = round(random.uniform(0.42, 0.50), 3)
        v2_score = round(random.uniform(0.46, 0.55), 3)
        v3_score = round(random.uniform(0.44, 0.53), 3)
        score = max(v1_score, v2_score, v3_score)
        verdict = "UNCERTAIN"
        defect_label = "Ambiguous Reflection / Glare"
        action = "REGRASP_TRIGGERED"
        instruction = INSTRUCTION_PICK_PRESENT
        final_cell_state = "REGRASP"
        cycle_s = round(random.uniform(5.6, 6.4), 2)
        views = [
            {"view": "inspect", "score": v1_score},
            {"view": "inspect_view2", "score": v2_score},
            {"view": "inspect_view3", "score": v3_score},
        ]
        reasoning = (
            f"Score ({score:.2f}) remained in UNCERTAIN band [{t_low:.2f}, {t_high:.2f}] across 3 wrist views. "
            f"Cell controller triggered REGRASP recovery."
        )
        state.hardware_metrics["regrasp_count"] += 1

    # 3. REASON: VLA SmolVLA / ACT on 12-core Xe3 iGPU
    await set_stage("REASON", "DECIDE")
    igpu_lat = round(random.uniform(23.2, 25.4), 2)
    state.hardware_metrics["igpu"]["latency_ms"] = igpu_lat
    await asyncio.sleep(0.45)

    # 4. ACT: SO-101 Follower Arm deterministic control on CPU
    act_cell_state = "PLACE_GOOD" if verdict == "GOOD" else ("PLACE_DEFECT" if verdict == "DEFECT" else "REGRASP")
    await set_stage("ACT", act_cell_state)
    cpu_lat = round(random.uniform(1.9, 2.3), 2)
    state.hardware_metrics["cpu"]["latency_ms"] = cpu_lat
    state.hardware_metrics["total_pipeline_latency_ms"] = round(npu_lat + igpu_lat + cpu_lat, 2)
    state.hardware_metrics["total_cycles_processed"] += 1
    await asyncio.sleep(0.5)

    # 5. OPTIMIZE: OpenVINO Heterogeneous Dispatch Telemetry
    await set_stage("OPTIMIZE", final_cell_state)
    await asyncio.sleep(0.3)

    # Generate media URLs (via Cloudinary or high-res synthesizer)
    media_res = upload_inspection_with_heatmap(
        brick_uuid=brick_uuid,
        raw_image_data=f"sim_{brick_uuid}",
        heatmap_image_data=f"heat_{brick_uuid}",
        defect_label=defect_label,
        score=score,
        color=chosen_color,
    )

    cycle_record = {
        "cycle_id": f"CYC-{brick_uuid}",
        "run_id": "sim-hub",
        "brick_idx": brick_idx,
        "timestamp": time.strftime("%H:%M:%S"),
        "color": chosen_color,
        "defect_label": defect_label,
        "verdict": verdict,
        "score": score,
        "anomaly_score": score,
        "t_low": t_low,
        "t_high": t_high,
        "views": views,
        "action": action,
        "instruction": instruction,
        "cell_state": final_cell_state,
        "model": "patchcore_256",
        "precision": "INT8",
        "device": "NPU",
        "latency_ms": npu_lat,
        "cycle_s": cycle_s,
        "evidence": "MOCK",
        "destination": "GOOD Bowl (Bowl 1)" if action == "PERFECT_BOWL" else ("DEFECTIVE Bowl (Bowl 2)" if action == "DEFECTIVE_BOWL" else "Inspection Camera (Re-orient)"),
        "root_cause_reasoning": reasoning,
        "nemotron_reasoning": reasoning,
        "nemotron_provider": "fallback",
        "similar_defects": [],
        "raw_url": media_res.get("raw_url"),
        "heatmap_url": media_res.get("heatmap_url", media_res.get("composite_heatmap_url")),
        "composite_url": media_res.get("composite_heatmap_url"),
        "media_provider": media_res.get("provider", "local_synthesizer"),
        "latencies": {
            "npu_anomalib_ms": npu_lat,
            "igpu_vla_ms": igpu_lat,
            "cpu_control_ms": cpu_lat,
            "npu_ms": npu_lat,
            "igpu_ms": igpu_lat,
            "cpu_ms": cpu_lat,
            "total_ms": state.hardware_metrics["total_pipeline_latency_ms"],
        },
        "openvino_dispatch": {
            "anomalib": "NPU (OpenVINO NPU Plugin / 50 TOPS)",
            "vla_policy": "GPU.0 (OpenVINO Xe3 / FP16)",
            "kinematics": "CPU (Intel TCC Deterministic Thread)",
        }
    }

    # Index 512-dim brick vector & find nearest historical defects (MariaDB 11.7+ VECTOR(512) / cosine fallback)
    emb = compute_brick_embedding(cycle_record.get("raw_url"), chosen_color, defect_label, score)
    cycle_record["similar_defects"] = await record_cycle_and_find_similar(cycle_record, emb, top_k=3)

    # Store in memory (latest first, keep max 40)
    state.recent_cycles.insert(0, cycle_record)
    if len(state.recent_cycles) > 40:
        state.recent_cycles.pop()
    _recompute_cycle_s_metrics()

    # Broadcast cycle event to UI
    await manager.broadcast({
        "type": "NEW_CYCLE",
        "cycle": cycle_record,
        "hardware_metrics": state.hardware_metrics,
        "t_low": state.t_low,
        "t_high": state.t_high,
        "cloud_providers": get_cloud_providers_status(),
    })

    # Trigger async cloud enrichment (Verda B300 Nemotron + Modal escalation webhook) off critical path
    _spawn_background_enrichment(cycle_record)

    await set_stage("IDLE", "HOME")
    return cycle_record


# FastAPI Lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("FastAPI Server Initialized for Intel Physical AI Challenge.")
    # Pre-populate 4 realistic historical cycles so dashboard looks populated right upon load
    colors = ["blue", "yellow", "red", "green"]
    outcomes = [
        ("GOOD", "None (Pristine)", 0.14, "PERFECT_BOWL", INSTRUCTION_PLACE_GOOD, "CONFIRM", 3.8, [{"view": "inspect", "score": 0.14}], "GOOD Bowl (Bowl 1)", "Pristine geometry verified by NPU PatchCore."),
        ("DEFECT", "Side Scratch / Deep Groove", 0.79, "DEFECTIVE_BOWL", INSTRUCTION_PLACE_DEFECT, "CONFIRM", 4.9, [{"view": "inspect", "score": 0.44}, {"view": "inspect_view2", "score": 0.79}], "DEFECTIVE Bowl (Bowl 2)", "Multi-view rotation revealed surface groove exceeding t_high 0.60."),
        ("UNCERTAIN", "Specular Reflection Glare", 0.51, "REGRASP_TRIGGERED", INSTRUCTION_PICK_PRESENT, "REGRASP", 5.8, [{"view": "inspect", "score": 0.46}, {"view": "inspect_view2", "score": 0.51}, {"view": "inspect_view3", "score": 0.49}], "Inspection Camera (Re-orient)", "Specular flare in UNCERTAIN band [0.35, 0.60] across 3 views; re-grasping."),
        ("GOOD", "None (Pristine)", 0.11, "PERFECT_BOWL", INSTRUCTION_PLACE_GOOD, "CONFIRM", 3.6, [{"view": "inspect", "score": 0.11}], "GOOD Bowl (Bowl 1)", "Full structural symmetry confirmed at 41.5 FPS.")
    ]
    for i, (verd, def_lbl, sc, act, instr, c_state, cyc_s, v_list, dest, reason) in enumerate(outcomes):
        uid = f"init_{i+1}"
        col = colors[i]
        media = upload_inspection_with_heatmap(
            brick_uuid=uid,
            raw_image_data=f"init_{uid}",
            heatmap_image_data=f"heat_{uid}",
            defect_label=def_lbl,
            score=sc,
            color=col,
        )
        rec = {
            "cycle_id": f"CYC-{uid}",
            "run_id": "seed-bootstrap",
            "brick_idx": i + 1,
            "timestamp": time.strftime("%H:%M:%S", time.localtime(time.time() - (4 - i) * 12)),
            "color": col,
            "defect_label": def_lbl,
            "verdict": verd,
            "score": sc,
            "anomaly_score": sc,
            "t_low": state.t_low,
            "t_high": state.t_high,
            "views": v_list,
            "action": act,
            "instruction": instr,
            "cell_state": c_state,
            "model": "patchcore_256",
            "precision": "INT8",
            "device": "NPU",
            "latency_ms": 9.4,
            "cycle_s": cyc_s,
            "evidence": "MOCK",
            "destination": dest,
            "root_cause_reasoning": reason,
            "nemotron_reasoning": reason,
            "nemotron_provider": "fallback",
            "similar_defects": [],
            "raw_url": media.get("raw_url"),
            "heatmap_url": media.get("heatmap_url", media.get("composite_heatmap_url")),
            "composite_url": media.get("composite_heatmap_url"),
            "media_provider": media.get("provider", "local_synthesizer"),
            "latencies": {
                "npu_anomalib_ms": 9.4,
                "igpu_vla_ms": 24.1,
                "cpu_control_ms": 2.1,
                "npu_ms": 9.4,
                "igpu_ms": 24.1,
                "cpu_ms": 2.1,
                "total_ms": 35.6,
            },
            "openvino_dispatch": {
                "anomalib": "NPU (50 TOPS)",
                "vla_policy": "GPU.0 (12 Xe3 Cores)",
                "kinematics": "CPU (Intel TCC)",
            }
        }
        emb = compute_brick_embedding(rec.get("raw_url"), col, def_lbl, sc)
        rec["similar_defects"] = await record_cycle_and_find_similar(rec, emb, top_k=3)
        state.recent_cycles.append(rec)
        state.hardware_metrics["total_cycles_processed"] += 1
        if act == "PERFECT_BOWL":
            state.hardware_metrics["perfect_count"] += 1
        elif act == "DEFECTIVE_BOWL":
            state.hardware_metrics["defective_count"] += 1
        else:
            state.hardware_metrics["regrasp_count"] += 1
    _recompute_cycle_s_metrics()

    # Backfill nearest neighbors across all 4 seed cycles (note: no background Nemotron/Modal calls on init_*)
    for rec in state.recent_cycles:
        rec["similar_defects"] = await find_similar_for_cycle_id(rec["cycle_id"], top_k=3)

    # Seed baseline OpenVINO device matrix (explicitly tagged MOCK until REAL/REPLAY arrives from ~/duplo-cell)
    existing_bench = await get_benchmarks(limit=50)
    if existing_bench.get("count", 0) == 0:
        await record_benchmarks([
            {
                "model": "patchcore_256",
                "device": "NPU",
                "precision": "INT8",
                "hint": "LATENCY",
                "latency_ms_p50": 9.4,
                "latency_ms_p95": 10.7,
                "fps": 106.4,
                "compile_s": 2.18,
                "cached_compile_s": 0.16,
                "size_mb": 14.2,
                "quality_metric": "image_F1",
                "quality": 0.94,
                "evidence": "MOCK",
            },
            {
                "model": "patchcore_256",
                "device": "GPU",
                "precision": "FP16",
                "hint": "LATENCY",
                "latency_ms_p50": 13.8,
                "latency_ms_p95": 16.1,
                "fps": 72.5,
                "compile_s": 1.64,
                "cached_compile_s": 0.14,
                "size_mb": 27.9,
                "quality_metric": "image_F1",
                "quality": 0.95,
                "evidence": "MOCK",
            },
            {
                "model": "patchcore_256",
                "device": "CPU",
                "precision": "FP32",
                "hint": "LATENCY",
                "latency_ms_p50": 34.6,
                "latency_ms_p95": 41.2,
                "fps": 28.9,
                "compile_s": 0.62,
                "cached_compile_s": 0.09,
                "size_mb": 55.4,
                "quality_metric": "image_F1",
                "quality": 0.95,
                "evidence": "MOCK",
            },
            {
                "model": "smolvla_duplo",
                "device": "GPU",
                "precision": "FP16",
                "hint": "LATENCY",
                "latency_ms_p50": 24.1,
                "latency_ms_p95": 27.4,
                "fps": 41.5,
                "compile_s": 3.85,
                "cached_compile_s": 0.31,
                "size_mb": 842.0,
                "quality_metric": "success_rate",
                "quality": 0.90,
                "evidence": "MOCK",
            },
        ])
    state.benchmarks = (await get_benchmarks(limit=50)).get("benchmarks", [])

    # Seed baseline policies & global threshold into MariaDB WITH SYSTEM VERSIONING audit table
    await record_policy_change(
        policy_id="global_anomaly_threshold",
        source="system_bootstrap",
        event_type="THRESHOLD_INIT",
        anomaly_threshold=state.active_anomaly_threshold,
        active_global_threshold=state.active_anomaly_threshold,
        target_brick_color="any",
        defect_description=f"Dual-threshold band t_low={state.t_low:.2f}, t_high={state.t_high:.2f} (active={state.active_anomaly_threshold:.2f})",
        action_on_match="DEFECTIVE_BOWL",
        is_active=True,
        reasoning="Initial calibrated threshold for Intel Core Ultra 50 TOPS NPU PatchCore.",
    )
    for r in state.active_rules:
        await record_policy_change(
            policy_id=r.rule_id,
            source="system_bootstrap",
            event_type="RULE_INIT",
            anomaly_threshold=r.anomaly_threshold,
            active_global_threshold=state.active_anomaly_threshold,
            target_brick_color=r.target_brick_color,
            defect_description=r.defect_description,
            action_on_match=r.action_on_match,
            is_active=getattr(r, "active", True),
            reasoning=r.reasoning,
        )

    yield
    # Shutdown
    if state.simulation_task and not state.simulation_task.done():
        state.simulation_running = False
        state.simulation_task.cancel()
    for bg_task in list(state.background_tasks):
        if not bg_task.done():
            bg_task.cancel()
    logger.info("FastAPI Server Shutdown complete.")

app = FastAPI(
    title="Intel Physical AI Inspection Cell - Floor Copilot Hub",
    description="Multimodal commissioning, Cloudinary media pipeline, and real-time Intel Core Ultra X9 388H telemetry.",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- WebSocket Endpoint ---
@app.websocket("/ws/live")
async def websocket_live_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send initial full state immediately upon connect
        await websocket.send_json({
            "type": "INITIAL_STATE",
            "stage": state.current_pipeline_stage,
            "cell_state": state.current_cell_state,
            "active_anomaly_threshold": state.active_anomaly_threshold,
            "t_low": state.t_low,
            "t_high": state.t_high,
            "active_rules": [r.model_dump() for r in state.active_rules],
            "recent_cycles": state.recent_cycles,
            "benchmarks": state.benchmarks,
            "hardware_metrics": state.hardware_metrics,
            "simulation_running": state.simulation_running,
            "cloud_providers": get_cloud_providers_status(),
        })
        while True:
            # Keep connection open and receive any ping/command from dashboard
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"WebSocket client error: {e}")
        manager.disconnect(websocket)


# --- REST API Endpoints ---

@app.get("/api/health")
async def health_check():
    return {
        "status": "online",
        "service": "Junction 2026 Physical AI Inspection Hub",
        "platform": state.hardware_metrics["platform"],
        "active_rules_count": len(state.active_rules),
        "total_cycles": state.hardware_metrics["total_cycles_processed"],
        "t_low": state.t_low,
        "t_high": state.t_high,
        "cloud_providers": get_cloud_providers_status(),
    }

@app.get("/api/state")
async def get_full_state():
    return {
        "stage": state.current_pipeline_stage,
        "cell_state": state.current_cell_state,
        "active_anomaly_threshold": state.active_anomaly_threshold,
        "t_low": state.t_low,
        "t_high": state.t_high,
        "active_rules": [r.model_dump() for r in state.active_rules],
        "recent_cycles": state.recent_cycles,
        "benchmarks": state.benchmarks,
        "hardware_metrics": state.hardware_metrics,
        "simulation_running": state.simulation_running,
        "cloud_providers": get_cloud_providers_status(),
    }

@app.get("/api/policy")
async def get_active_policy():
    """
    Returns the current active sorting rules and dual anomaly thresholds (`t_low`, `t_high`,
    `active_anomaly_threshold`) for the edge robot loop.
    """
    return {
        "active_anomaly_threshold": state.active_anomaly_threshold,
        "anomaly_threshold": state.active_anomaly_threshold,
        "t_low": state.t_low,
        "t_high": state.t_high,
        "rules_count": len(state.active_rules),
        "rules": [r.model_dump() for r in state.active_rules if getattr(r, 'active', True)],
        "regrasp_range": [state.t_low, state.t_high],
        "studio_tasks": [
            INSTRUCTION_PICK_PRESENT,
            INSTRUCTION_PLACE_GOOD,
            INSTRUCTION_PLACE_DEFECT,
        ],
        "skills": {
            "pick_present": INSTRUCTION_PICK_PRESENT,
            "place_good": INSTRUCTION_PLACE_GOOD,
            "place_defect": INSTRUCTION_PLACE_DEFECT,
        },
        "openvino_acceleration": {
            "npu_anomalib": "OpenVINO NPU Plugin (50 TOPS)",
            "igpu_vla": "OpenVINO Xe3 FP16 (12 Cores)",
            "cpu_control": "Intel TCC Real-Time Deterministic Thread",
        },
        "last_updated": time.strftime("%H:%M:%S"),
    }


@app.post("/api/cell-state")
async def update_cell_state(event_req: CellStateEventRequest):
    """
    Receives live state transitions tailed from `runs/<run_id>/events.jsonl`
    (`HOME`, `PICK_PRESENT`, `SNAP_TO_INSPECT`, `CHECK_HELD`, `INSPECT`, `DECIDE`,
    `PLACE_GOOD`, `PLACE_DEFECT`, `NEXT_VIEW`, `REGRASP`, `CONFIRM`, `DONE`, `FAULT`).
    """
    c_state = (event_req.cell_state or "HOME").strip().upper()
    stage = map_cell_state_to_pipeline_stage(c_state)
    state.current_cell_state = c_state
    state.current_pipeline_stage = stage

    await manager.broadcast({
        "type": "STAGE_CHANGE",
        "stage": stage,
        "cell_state": c_state,
        "run_id": event_req.run_id,
        "brick_idx": event_req.brick_idx,
        "event": event_req.event,
        "instruction": event_req.instruction,
        "verdict": event_req.verdict,
        "score": event_req.score,
        "evidence": event_req.evidence,
        "timestamp": time.time(),
    })
    return {
        "status": "success",
        "stage": stage,
        "cell_state": c_state,
    }


@app.get("/api/benchmarks")
async def list_openvino_benchmarks(limit: int = 50):
    """
    Returns OpenVINO device benchmark records (`~/duplo-cell/reports/bench/*.json`)
    ordered by evidence (`REAL` -> `REPLAY` -> `MOCK`), model, and device.
    """
    res = await get_benchmarks(limit=limit)
    state.benchmarks = res.get("benchmarks", [])
    return {
        "status": "success",
        **res,
    }


@app.post("/api/benchmarks")
async def ingest_openvino_benchmarks(
    payload: Union[BenchmarkRecord, List[BenchmarkRecord], Dict[str, Any]] = Body(...),
):
    """
    Ingests one or multiple OpenVINO benchmark records (`~/duplo-cell/reports/bench/*.json`)
    from `duplo_cell_bridge.py` or `optimize/bench.py` and broadcasts `BENCHMARKS_UPDATED`.
    """
    raw_items: List[Dict[str, Any]] = []
    if isinstance(payload, BenchmarkRecord):
        raw_items = [payload.model_dump()]
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, BenchmarkRecord):
                raw_items.append(item.model_dump())
            elif isinstance(item, dict):
                raw_items.append(item)
    elif isinstance(payload, dict):
        if isinstance(payload.get("benchmarks"), list):
            raw_items = [r for r in payload["benchmarks"] if isinstance(r, dict)]
        elif payload.get("model"):
            raw_items = [payload]

    if not raw_items:
        raise HTTPException(status_code=400, detail="No valid benchmark records provided.")

    saved = await record_benchmarks(raw_items)
    latest_res = await get_benchmarks(limit=50)
    state.benchmarks = latest_res.get("benchmarks", saved)

    # Reflect REAL/REPLAY hardware latencies into live telemetry cards when available
    for rec in saved:
        if rec.get("evidence") in ("REAL", "REPLAY"):
            dev = str(rec.get("device") or "").upper()
            p50 = float(rec.get("latency_ms_p50") or 0.0)
            fps = float(rec.get("fps") or 0.0)
            model_name = str(rec.get("model") or "")
            prec = str(rec.get("precision") or "")
            if dev == "NPU" and p50 > 0:
                state.hardware_metrics["npu"]["latency_ms"] = round(p50, 2)
                state.hardware_metrics["npu"]["workload"] = f"Anomalib ({model_name} · {prec})"
            elif dev in ("GPU", "IGPU") and p50 > 0 and ("vla" in model_name.lower() or "act" in model_name.lower() or "policy" in model_name.lower()):
                state.hardware_metrics["igpu"]["latency_ms"] = round(p50, 2)
                if fps > 0:
                    state.hardware_metrics["igpu"]["throughput_fps"] = round(fps, 1)
                state.hardware_metrics["igpu"]["precision"] = f"{prec} / OpenVINO"
    state.hardware_metrics["total_pipeline_latency_ms"] = round(
        float(state.hardware_metrics["npu"]["latency_ms"])
        + float(state.hardware_metrics["igpu"]["latency_ms"])
        + float(state.hardware_metrics["cpu"]["latency_ms"]),
        2,
    )

    await manager.broadcast({
        "type": "BENCHMARKS_UPDATED",
        "benchmarks": state.benchmarks,
        "hardware_metrics": state.hardware_metrics,
    })

    return {
        "status": "success",
        "ingested": len(saved),
        "count": len(state.benchmarks),
        "benchmarks": state.benchmarks,
    }


@app.patch("/api/cycles/{brick_uuid}/nemotron")
async def update_cycle_nemotron(brick_uuid: str, update: NemotronUpdateRequest):
    """
    Accepts updates from Cloud Nemotron 3.5 Super VL worker to annotate a cycle
    with deeper multimodal root-cause analysis and optionally dynamically tune anomaly threshold.
    Broadcasts the updated state over /ws/live.
    """
    target_id = f"CYC-{brick_uuid}" if not brick_uuid.startswith("CYC-") else brick_uuid
    found_cycle = None
    for cyc in state.recent_cycles:
        if cyc.get("cycle_id") == target_id or cyc.get("cycle_id") == f"CYC-{brick_uuid}":
            cyc["nemotron_reasoning"] = update.nemotron_root_cause
            cyc["root_cause_reasoning"] = update.nemotron_root_cause
            cyc["nemotron_manual_patch"] = True
            found_cycle = cyc
            break

    if not found_cycle:
        raise HTTPException(status_code=404, detail=f"Cycle '{brick_uuid}' not found in recent cycles.")

    if update.adjusted_threshold is not None:
        state.active_anomaly_threshold = float(update.adjusted_threshold)
        logger.info(f"Nemotron updated active anomaly threshold to {update.adjusted_threshold}")
        await record_policy_change(
            policy_id="global_anomaly_threshold",
            source="nemotron_worker",
            event_type="THRESHOLD_TUNED",
            anomaly_threshold=state.active_anomaly_threshold,
            active_global_threshold=state.active_anomaly_threshold,
            target_brick_color=str(found_cycle.get("color", "any")),
            defect_description=str(found_cycle.get("defect_label", "")),
            action_on_match=str(found_cycle.get("action", "DEFECTIVE_BOWL")),
            is_active=True,
            reasoning=update.nemotron_root_cause,
        )

    await manager.broadcast({
        "type": "CYCLE_UPDATED",
        "cycle": found_cycle,
        "active_anomaly_threshold": state.active_anomaly_threshold,
        "t_low": state.t_low,
        "t_high": state.t_high,
        "cloud_providers": get_cloud_providers_status(),
    })

    return {
        "status": "success",
        "cycle_id": target_id,
        "nemotron_root_cause": update.nemotron_root_cause,
        "active_anomaly_threshold": state.active_anomaly_threshold,
    }


@app.get("/api/policies/history")
async def get_sorting_policies_history(limit: int = 50):
    """
    Returns the temporal audit trail of sorting policies and dynamic anomaly threshold
    mutations powered by MariaDB `WITH SYSTEM VERSIONING` (`FOR SYSTEM_TIME ALL`).
    """
    res = await get_policy_history(limit=limit)
    return {
        "status": "success",
        "active_anomaly_threshold": state.active_anomaly_threshold,
        "t_low": state.t_low,
        "t_high": state.t_high,
        **res,
    }


@app.get("/api/cycles/{cycle_id}/similar")
async def get_similar_cycles(cycle_id: str, top_k: int = 3):
    """
    Queries MariaDB 11.7+ VECTOR(512) (VEC_DISTANCE_COSINE) or the in-memory 512-dim
    cosine similarity fallback for the top-k nearest historical inspection cycles.
    """
    matches = await find_similar_for_cycle_id(cycle_id, top_k=max(1, min(top_k, 10)))
    db_status = get_mariadb_status()
    return {
        "status": "success",
        "cycle_id": cycle_id,
        "provider": db_status.get("mode", "FALLBACK"),
        "detail": db_status.get("detail", ""),
        "similar_defects": matches,
    }


@app.post("/api/cycles")
async def ingest_edge_telemetry(payload: CycleIngestRequest):
    """
    Ingests live telemetry from `~/duplo-cell` (`InspectionResult` / `events.jsonl` via
    `duplo_cell_bridge.py`) as well as legacy Hub payloads.
    Maps `verdict` <-> `action`, tracks `t_low`/`t_high`/`views`/`instruction`/`cell_state`/`cycle_s`/`evidence`,
    indexes 512-dim vectors into MariaDB, broadcasts over `/ws/live`, and dispatches async cloud enrichment.
    """
    # 1. Resolve dual thresholds (`t_low` & `t_high`)
    if payload.t_low is not None and 0.0 <= float(payload.t_low) <= 1.0:
        state.t_low = round(float(payload.t_low), 4)
    if payload.t_high is not None and 0.0 <= float(payload.t_high) <= 1.0:
        state.t_high = round(float(payload.t_high), 4)
    effective_t_low = state.t_low
    effective_t_high = state.t_high

    # 2. Resolve multi-view scores & max score per CONTRACTS.md
    views_list: List[Dict[str, Any]] = []
    if payload.views:
        for v in payload.views:
            views_list.append({"view": str(v.view or "inspect"), "score": round(float(v.score), 4)})

    if payload.score is not None:
        effective_score = round(float(payload.score), 4)
    elif payload.anomaly_score is not None:
        effective_score = round(float(payload.anomaly_score), 4)
    elif views_list:
        effective_score = round(max(float(v["score"]) for v in views_list), 4)
    else:
        effective_score = 0.12

    if not views_list:
        views_list = [{"view": "inspect", "score": effective_score}]

    # 3. Bidirectional verdict <-> action & exact VLA instruction
    verdict, action = resolve_verdict_and_action(
        verdict=payload.verdict,
        action=payload.action,
        score=effective_score,
        t_low=effective_t_low,
        t_high=effective_t_high,
    )
    instruction = resolve_vla_instruction(payload.instruction, verdict, action)

    # 4. Resolve brick_uuid & cycle_id
    if payload.brick_uuid and payload.brick_uuid.strip():
        brick_uuid = payload.brick_uuid.strip()
    elif payload.run_id and payload.brick_idx is not None:
        safe_run = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in payload.run_id)[:36]
        brick_uuid = f"{safe_run}_b{int(payload.brick_idx):04d}"
    elif payload.brick_idx is not None:
        brick_uuid = f"brick_{int(payload.brick_idx):04d}_{str(uuid.uuid4())[:4]}"
    else:
        brick_uuid = str(uuid.uuid4())[:8]

    color = (payload.color or "blue").strip().lower() or "blue"
    if payload.defect_label and payload.defect_label.strip():
        defect_label = payload.defect_label.strip()
    else:
        if verdict == "GOOD":
            defect_label = "None (Pristine)"
        elif verdict == "DEFECT":
            defect_label = "Surface Anomaly Detected"
        elif verdict == "NO_BRICK":
            defect_label = "Empty Gripper (NO_BRICK)"
        else:
            defect_label = "Uncertain Boundary (Multi-View)"

    # 5. Resolve evidence label (`REAL` | `REPLAY` | `MOCK`)
    ev_raw = (payload.evidence or "").strip().upper()
    if ev_raw in ("REAL", "REPLAY", "MOCK"):
        evidence = ev_raw
    elif payload.run_id and ("fake" in payload.run_id.lower() or "replay" in payload.run_id.lower()):
        evidence = "REPLAY"
    elif payload.run_id and "mock" in payload.run_id.lower():
        evidence = "MOCK"
    elif payload.run_id:
        evidence = "REAL"
    else:
        evidence = "REPLAY"

    # 6. Resolve device, model, precision, and stage latencies
    device_name = (payload.device or "NPU").strip().upper() or "NPU"
    model_name = (payload.model or "patchcore_256").strip() or "patchcore_256"
    precision_name = (payload.precision or "INT8").strip().upper() or "INT8"

    npu_lat = payload.npu_latency_ms
    igpu_lat = payload.igpu_latency_ms
    cpu_lat = payload.cpu_latency_ms

    if payload.latency_ms is not None:
        if device_name == "NPU" and npu_lat is None:
            npu_lat = float(payload.latency_ms)
        elif device_name in ("GPU", "IGPU") and igpu_lat is None:
            igpu_lat = float(payload.latency_ms)
        elif device_name == "CPU" and cpu_lat is None:
            cpu_lat = float(payload.latency_ms)

    npu_lat = round(float(npu_lat if npu_lat is not None else 9.4), 2)
    igpu_lat = round(float(igpu_lat if igpu_lat is not None else 24.1), 2)
    cpu_lat = round(float(cpu_lat if cpu_lat is not None else 2.1), 2)
    tot_lat = round(npu_lat + igpu_lat + cpu_lat, 2)
    inspector_lat = round(float(payload.latency_ms if payload.latency_ms is not None else npu_lat), 2)

    cell_state = (payload.cell_state or "").strip().upper()
    if not cell_state:
        if verdict == "NO_BRICK":
            cell_state = "CHECK_HELD"
        elif action == "REGRASP_TRIGGERED":
            cell_state = "REGRASP"
        else:
            cell_state = "CONFIRM"

    state.current_cell_state = cell_state
    state.current_pipeline_stage = map_cell_state_to_pipeline_stage(cell_state)

    # 7. Media handling (normalize raw/heatmap base64 URIs; if only heatmap PNG was saved in runs/<id>/heatmaps, use raw fallback or heatmap)
    norm_raw = normalize_image_uri(payload.raw_image_b64)
    norm_heat = normalize_image_uri(payload.heatmap_image_b64)
    norm_top = normalize_image_uri(payload.top_image_b64)

    media_res = upload_inspection_with_heatmap(
        brick_uuid=brick_uuid,
        raw_image_data=norm_raw or f"raw_{brick_uuid}",
        heatmap_image_data=norm_heat or f"heat_{brick_uuid}",
        defect_label=defect_label,
        score=effective_score,
        color=color,
    )

    if payload.root_cause and payload.root_cause.strip():
        reason_text = payload.root_cause.strip()
    else:
        views_summary = ", ".join(f"{v['view']}={v['score']:.2f}" for v in views_list)
        reason_text = (
            f"{model_name} ({precision_name} on {device_name}, {inspector_lat:.1f}ms) -> "
            f"verdict {verdict} (max score {effective_score:.2f} vs [{effective_t_low:.2f}, {effective_t_high:.2f}]; views: {views_summary}). "
            f"VLA instruction: \"{instruction}\""
        )

    ts_display = time.strftime("%H:%M:%S")
    if payload.ts and "T" in payload.ts:
        try:
            time_part = payload.ts.split("T", 1)[1]
            for sep in ("+", "-", "Z"):
                if sep in time_part:
                    time_part = time_part.split(sep, 1)[0]
                    break
            if len(time_part) >= 8:
                ts_display = time_part[:8]
        except Exception:
            pass

    cycle_id_str = f"CYC-{brick_uuid}" if not brick_uuid.startswith("CYC-") else brick_uuid
    cycle_s_val = round(float(payload.cycle_s), 2) if payload.cycle_s is not None else None

    cycle_record: Dict[str, Any] = {
        "cycle_id": cycle_id_str,
        "run_id": payload.run_id,
        "brick_idx": payload.brick_idx,
        "ts": payload.ts,
        "timestamp": ts_display,
        "color": color,
        "defect_label": defect_label,
        "verdict": verdict,
        "score": effective_score,
        "anomaly_score": effective_score,
        "t_low": effective_t_low,
        "t_high": effective_t_high,
        "views": views_list,
        "heatmap_png": payload.heatmap_png,
        "action": action,
        "instruction": instruction,
        "cell_state": cell_state,
        "model": model_name,
        "precision": precision_name,
        "device": device_name,
        "latency_ms": inspector_lat,
        "cycle_s": cycle_s_val,
        "stage_durations_s": payload.stage_durations_s,
        "evidence": evidence,
        "destination": (
            "GOOD Bowl (Bowl 1)"
            if action == "PERFECT_BOWL"
            else ("DEFECTIVE Bowl (Bowl 2)" if action == "DEFECTIVE_BOWL" else "Inspection Camera (Re-orient / Re-grasp)")
        ),
        "root_cause_reasoning": reason_text,
        "nemotron_reasoning": reason_text,
        "nemotron_provider": "fallback",
        "similar_defects": [],
        "raw_url": media_res.get("raw_url"),
        "heatmap_url": media_res.get("heatmap_url", media_res.get("composite_heatmap_url")),
        "composite_url": media_res.get("composite_heatmap_url"),
        "top_url": norm_top,
        "media_provider": media_res.get("provider", "local_synthesizer"),
        "latencies": {
            "npu_anomalib_ms": npu_lat,
            "igpu_vla_ms": igpu_lat,
            "cpu_control_ms": cpu_lat,
            "npu_ms": npu_lat,
            "igpu_ms": igpu_lat,
            "cpu_ms": cpu_lat,
            "total_ms": tot_lat,
        },
        "openvino_dispatch": {
            "anomalib": f"{device_name} ({model_name} · {precision_name})",
            "vla_policy": "GPU.0 (12 Xe3 Cores)",
            "kinematics": "CPU (Intel TCC)",
        },
    }

    emb = compute_brick_embedding(
        norm_raw or norm_heat or cycle_record.get("raw_url"),
        color,
        defect_label,
        effective_score,
    )
    cycle_record["similar_defects"] = await record_cycle_and_find_similar(cycle_record, emb, top_k=3)

    # Deduplicate if an earlier update for the same cycle_id exists
    replaced_old = None
    for idx, existing in enumerate(state.recent_cycles):
        if existing.get("cycle_id") == cycle_id_str:
            replaced_old = state.recent_cycles.pop(idx)
            break

    if replaced_old is not None:
        old_act = replaced_old.get("action")
        if old_act == "PERFECT_BOWL":
            state.hardware_metrics["perfect_count"] = max(0, state.hardware_metrics["perfect_count"] - 1)
        elif old_act == "DEFECTIVE_BOWL":
            state.hardware_metrics["defective_count"] = max(0, state.hardware_metrics["defective_count"] - 1)
        else:
            state.hardware_metrics["regrasp_count"] = max(0, state.hardware_metrics["regrasp_count"] - 1)
    else:
        state.hardware_metrics["total_cycles_processed"] += 1

    state.recent_cycles.insert(0, cycle_record)
    if len(state.recent_cycles) > 40:
        state.recent_cycles.pop()

    state.hardware_metrics["npu"]["latency_ms"] = npu_lat
    state.hardware_metrics["igpu"]["latency_ms"] = igpu_lat
    state.hardware_metrics["cpu"]["latency_ms"] = cpu_lat
    state.hardware_metrics["total_pipeline_latency_ms"] = tot_lat
    if action == "PERFECT_BOWL":
        state.hardware_metrics["perfect_count"] += 1
    elif action == "DEFECTIVE_BOWL":
        state.hardware_metrics["defective_count"] += 1
    else:
        state.hardware_metrics["regrasp_count"] += 1
    _recompute_cycle_s_metrics()

    await manager.broadcast({
        "type": "NEW_CYCLE",
        "cycle": cycle_record,
        "hardware_metrics": state.hardware_metrics,
        "t_low": state.t_low,
        "t_high": state.t_high,
        "cell_state": state.current_cell_state,
        "cloud_providers": get_cloud_providers_status(),
    })

    _spawn_background_enrichment(cycle_record)

    return {
        "status": "success",
        "cycle_id": cycle_record["cycle_id"],
        "verdict": verdict,
        "action": action,
        "instruction": instruction,
        "evidence": evidence,
    }


@app.post("/api/simulate-cycle")
async def trigger_simulate_cycle(outcome: Optional[str] = None):
    """
    Manually triggers one realistic inspection cycle (PERFECT, DEFECTIVE, or REGRASP).
    """
    cycle = await execute_full_cycle_simulation(outcome)
    return {"status": "success", "cycle": cycle}


@app.post("/api/toggle-simulation")
async def toggle_continuous_simulation():
    """
    Toggles automated pitch presentation cycle generation loop.
    """
    state.simulation_running = not state.simulation_running
    if state.simulation_running:
        state.simulation_task = asyncio.create_task(continuous_simulator_loop())
    else:
        if state.simulation_task:
            state.simulation_task.cancel()

    await manager.broadcast({
        "type": "SIMULATION_STATUS",
        "simulation_running": state.simulation_running,
    })
    return {"simulation_running": state.simulation_running}


@app.post("/api/copilot/rule")
async def create_copilot_rule(
    text_instruction: str = Form(""),
    image: Optional[UploadFile] = File(None),
    audio: Optional[UploadFile] = File(None),
):
    """
    Multimodal floor copilot endpoint powered by Gemini 3.8 Flash.
    Accepts operator voice audio, webcam image, or text prompt.
    Returns structured SortingRule with spoken_confirmation.
    """
    image_bytes = None
    audio_bytes = None

    if image:
        image_bytes = await image.read()
    if audio:
        audio_bytes = await audio.read()

    rule = extract_rule_from_multimodal(
        image_bytes=image_bytes,
        audio_bytes=audio_bytes,
        text_instruction=text_instruction,
    )

    # Check if duplicate rule_id exists; if so, update or make unique
    existing_idx = next((i for i, r in enumerate(state.active_rules) if r.rule_id == rule.rule_id), None)
    if existing_idx is not None:
        state.active_rules[existing_idx] = rule
    else:
        state.active_rules.insert(0, rule)

    # Update active threshold if specified
    if getattr(rule, "anomaly_threshold", None):
        state.active_anomaly_threshold = float(rule.anomaly_threshold)
        logger.info(f"Gemini Copilot updated active anomaly threshold to {rule.anomaly_threshold}")

    await record_policy_change(
        policy_id=rule.rule_id,
        source="gemini_copilot",
        event_type="RULE_UPDATED" if existing_idx is not None else "RULE_CREATED",
        anomaly_threshold=float(getattr(rule, "anomaly_threshold", state.active_anomaly_threshold)),
        active_global_threshold=state.active_anomaly_threshold,
        target_brick_color=rule.target_brick_color,
        defect_description=rule.defect_description,
        action_on_match=rule.action_on_match,
        is_active=True,
        reasoning=rule.reasoning,
    )

    # Broadcast updated rules over WebSocket
    await manager.broadcast({
        "type": "RULE_CREATED",
        "rule": rule.model_dump(),
        "active_rules": [r.model_dump() for r in state.active_rules],
        "active_anomaly_threshold": state.active_anomaly_threshold,
    })

    return {
        "status": "success",
        "rule": rule.model_dump(),
        "spoken_confirmation": rule.spoken_confirmation,
    }

@app.delete("/api/copilot/rule/{rule_id}")
async def delete_copilot_rule(rule_id: str):
    """
    Deletes an active sorting rule and logs temporal deactivation in MariaDB WITH SYSTEM VERSIONING.
    """
    removed = next((r for r in state.active_rules if r.rule_id == rule_id), None)
    state.active_rules = [r for r in state.active_rules if r.rule_id != rule_id]
    await record_policy_change(
        policy_id=rule_id,
        source="operator_ui",
        event_type="RULE_DELETED",
        anomaly_threshold=float(getattr(removed, "anomaly_threshold", state.active_anomaly_threshold)) if removed else state.active_anomaly_threshold,
        active_global_threshold=state.active_anomaly_threshold,
        target_brick_color=removed.target_brick_color if removed else "any",
        defect_description=removed.defect_description if removed else "Deleted sorting rule",
        action_on_match=removed.action_on_match if removed else "DEFECTIVE_BOWL",
        is_active=False,
        reasoning="Deactivated by operator via Mission Control UI.",
    )
    await manager.broadcast({
        "type": "RULE_DELETED",
        "rule_id": rule_id,
        "active_rules": [r.model_dump() for r in state.active_rules],
    })
    return {"status": "success", "rule_id": rule_id}

@app.post("/mock-modal")
async def mock_modal_webhook(payload: Dict[str, Any]):
    """
    Local mock endpoint simulating the Modal serverless escalation & retraining webhook.
    Uses the exact same audit evaluator as `modal deploy backend/modal_webhook.py`.
    """
    logger.info("Received local Modal escalation callback for cycle: %s", payload.get("cycle_id", "unknown"))
    return evaluate_escalation_payload(payload)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
