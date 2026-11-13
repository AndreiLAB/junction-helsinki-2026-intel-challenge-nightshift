import os
import uuid
import time
import random
import asyncio
import logging
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from cloudinary_media import upload_inspection_with_heatmap, create_simulated_brick_image
from gemini_copilot import extract_rule_from_multimodal, SortingRule

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("junction_backend")

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
        self.recent_cycles: List[Dict[str, Any]] = []
        self.current_pipeline_stage: str = "IDLE" # IDLE, PERCEIVE, DETECT, REASON, ACT, OPTIMIZE
        self.simulation_running: bool = False
        self.simulation_task: Optional[asyncio.Task] = None

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
            "total_cycles_processed": 0,
            "perfect_count": 0,
            "defective_count": 0,
            "regrasp_count": 0,
        }

state = SystemState()

# Pydantic models for incoming telemetry
class CycleIngestRequest(BaseModel):
    brick_uuid: Optional[str] = None
    color: str = "blue"
    defect_label: str = "Pristine"
    anomaly_score: float = 0.12
    action: str = "PERFECT_BOWL"
    root_cause: Optional[str] = None
    npu_latency_ms: Optional[float] = 9.4
    igpu_latency_ms: Optional[float] = 24.1
    cpu_latency_ms: Optional[float] = 2.1
    raw_image_b64: Optional[str] = None
    heatmap_image_b64: Optional[str] = None

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

async def set_stage(stage: str):
    state.current_pipeline_stage = stage
    await manager.broadcast({
        "type": "STAGE_CHANGE",
        "stage": stage,
        "timestamp": time.time(),
    })

async def execute_full_cycle_simulation(outcome_type: Optional[str] = None):
    """
    Executes a high-fidelity physical AI cycle stepping through:
    PERCEIVE -> DETECT -> REASON -> ACT -> OPTIMIZE -> IDLE
    """
    brick_uuid = str(uuid.uuid4())[:8]
    colors = ["blue", "yellow", "red", "green", "orange"]
    chosen_color = random.choice(colors)

    if outcome_type is None:
        outcome_type = random.choice(["PERFECT", "DEFECTIVE", "REGRASP"])

    # 1. PERCEIVE: Camera frame acquisition
    await set_stage("PERCEIVE")
    await asyncio.sleep(0.35)

    # 2. DETECT: Anomalib v2.7.0 on 50 TOPS NPU
    await set_stage("DETECT")
    npu_lat = round(random.uniform(8.9, 9.8), 2)
    state.hardware_metrics["npu"]["latency_ms"] = npu_lat
    await asyncio.sleep(0.4)

    if outcome_type == "PERFECT":
        score = round(random.uniform(0.08, 0.22), 3)
        defect_label = "None (Pristine)"
        action = "PERFECT_BOWL"
        reasoning = (
            f"Anomalib PatchCore on 50 TOPS NPU detected zero topological variance (score: {score:.2f}). "
            f"Core Ultra Xe3 VLA planned direct trajectory to Accept Bowl 1. 0% defect likelihood."
        )
        state.hardware_metrics["perfect_count"] += 1
    elif outcome_type == "DEFECTIVE":
        score = round(random.uniform(0.68, 0.92), 3)
        defect_label = random.choice([
            "Side Scratch / Deep Groove",
            "Cracked Stud Alignment",
            "Marker Stripe Contamination",
            "Chipped Corner Flaw"
        ])
        action = "DEFECTIVE_BOWL"
        reasoning = (
            f"Anomalib localized anomaly cluster on upper quadrant (score: {score:.2f} > threshold 0.55). "
            f"SmolVLA task policy committed rejection actuation to Discard Bowl 2."
        )
        state.hardware_metrics["defective_count"] += 1
    else: # REGRASP
        score = round(random.uniform(0.48, 0.54), 3)
        defect_label = "Ambiguous Reflection / Glare"
        action = "REGRASP_TRIGGERED"
        reasoning = (
            f"Borderline score ({score:.2f}) near decision boundary. "
            f"SmolVLA uncertainty policy triggered wrist re-orientation to eliminate glare."
        )
        state.hardware_metrics["regrasp_count"] += 1

    # 3. REASON: VLA SmolVLA / ACT on 12-core Xe3 iGPU
    await set_stage("REASON")
    igpu_lat = round(random.uniform(23.2, 25.4), 2)
    state.hardware_metrics["igpu"]["latency_ms"] = igpu_lat
    await asyncio.sleep(0.45)

    # 4. ACT: SO-101 Follower Arm deterministic control on CPU
    await set_stage("ACT")
    cpu_lat = round(random.uniform(1.9, 2.3), 2)
    state.hardware_metrics["cpu"]["latency_ms"] = cpu_lat
    state.hardware_metrics["total_pipeline_latency_ms"] = round(npu_lat + igpu_lat + cpu_lat, 2)
    state.hardware_metrics["total_cycles_processed"] += 1
    await asyncio.sleep(0.5)

    # 5. OPTIMIZE: OpenVINO Heterogeneous Dispatch Telemetry
    await set_stage("OPTIMIZE")
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
        "timestamp": time.strftime("%H:%M:%S"),
        "color": chosen_color,
        "defect_label": defect_label,
        "anomaly_score": score,
        "action": action,
        "destination": "Bowl 1 (Accept)" if action == "PERFECT_BOWL" else ("Bowl 2 (Defective)" if action == "DEFECTIVE_BOWL" else "Inspection Turntable"),
        "root_cause_reasoning": reasoning,
        "raw_url": media_res.get("raw_url"),
        "heatmap_url": media_res.get("heatmap_url", media_res.get("composite_heatmap_url")),
        "composite_url": media_res.get("composite_heatmap_url"),
        "latencies": {
            "npu_anomalib_ms": npu_lat,
            "igpu_vla_ms": igpu_lat,
            "cpu_control_ms": cpu_lat,
            "total_ms": state.hardware_metrics["total_pipeline_latency_ms"],
        },
        "openvino_dispatch": {
            "anomalib": "NPU (OpenVINO NPU Plugin / 50 TOPS)",
            "vla_policy": "GPU.0 (OpenVINO Xe3 / FP16)",
            "kinematics": "CPU (Intel TCC Deterministic Thread)",
        }
    }

    # Store in memory (latest first, keep max 40)
    state.recent_cycles.insert(0, cycle_record)
    if len(state.recent_cycles) > 40:
        state.recent_cycles.pop()

    # Broadcast cycle event to UI
    await manager.broadcast({
        "type": "NEW_CYCLE",
        "cycle": cycle_record,
        "hardware_metrics": state.hardware_metrics,
    })

    await set_stage("IDLE")
    return cycle_record


# FastAPI Lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("FastAPI Server Initialized for Intel Physical AI Challenge.")
    # Pre-populate 4 realistic historical cycles so dashboard looks populated right upon load
    colors = ["blue", "yellow", "red", "green"]
    outcomes = [
        ("PERFECT", "None (Pristine)", 0.14, "PERFECT_BOWL", "Bowl 1 (Accept)", "Pristine geometry verified by NPU PatchCore."),
        ("DEFECTIVE", "Side Scratch / Deep Groove", 0.79, "DEFECTIVE_BOWL", "Bowl 2 (Defective)", "Significant topological surface groove exceeding 0.55 limit."),
        ("REGRASP", "Specular Reflection Glare", 0.51, "REGRASP_TRIGGERED", "Inspection Turntable", "Specular flare on high-gloss cyan stud causing edge ambiguity."),
        ("PERFECT", "None (Pristine)", 0.11, "PERFECT_BOWL", "Bowl 1 (Accept)", "Full structural symmetry confirmed at 41.5 FPS.")
    ]
    for i, (out, def_lbl, sc, act, dest, reason) in enumerate(outcomes):
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
            "timestamp": time.strftime("%H:%M:%S", time.localtime(time.time() - (4 - i) * 12)),
            "color": col,
            "defect_label": def_lbl,
            "anomaly_score": sc,
            "action": act,
            "destination": dest,
            "root_cause_reasoning": reason,
            "raw_url": media.get("raw_url"),
            "heatmap_url": media.get("heatmap_url", media.get("composite_heatmap_url")),
            "composite_url": media.get("composite_heatmap_url"),
            "latencies": {
                "npu_anomalib_ms": 9.4,
                "igpu_vla_ms": 24.1,
                "cpu_control_ms": 2.1,
                "total_ms": 35.6,
            },
            "openvino_dispatch": {
                "anomalib": "NPU (50 TOPS)",
                "vla_policy": "GPU.0 (12 Xe3 Cores)",
                "kinematics": "CPU (Intel TCC)",
            }
        }
        state.recent_cycles.append(rec)
        state.hardware_metrics["total_cycles_processed"] += 1
        if act == "PERFECT_BOWL":
            state.hardware_metrics["perfect_count"] += 1
        elif act == "DEFECTIVE_BOWL":
            state.hardware_metrics["defective_count"] += 1
        else:
            state.hardware_metrics["regrasp_count"] += 1

    yield
    # Shutdown
    if state.simulation_task and not state.simulation_task.done():
        state.simulation_running = False
        state.simulation_task.cancel()
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
            "active_rules": [r.model_dump() for r in state.active_rules],
            "recent_cycles": state.recent_cycles,
            "hardware_metrics": state.hardware_metrics,
            "simulation_running": state.simulation_running,
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
    }

@app.get("/api/state")
async def get_full_state():
    return {
        "stage": state.current_pipeline_stage,
        "active_rules": [r.model_dump() for r in state.active_rules],
        "recent_cycles": state.recent_cycles,
        "hardware_metrics": state.hardware_metrics,
        "simulation_running": state.simulation_running,
    }

@app.post("/api/cycles")
async def ingest_edge_telemetry(payload: CycleIngestRequest):
    """
    Ingests live telemetry streamed from Member 2/3 robot state machine & Anomalib/VLA models.
    Broadcasts cycle to all dashboard WebSocket clients.
    """
    brick_uuid = payload.brick_uuid or str(uuid.uuid4())[:8]

    # Media handling
    media_res = upload_inspection_with_heatmap(
        brick_uuid=brick_uuid,
        raw_image_data=payload.raw_image_b64 or f"raw_{brick_uuid}",
        heatmap_image_data=payload.heatmap_image_b64 or f"heat_{brick_uuid}",
        defect_label=payload.defect_label,
        score=payload.anomaly_score,
        color=payload.color,
    )

    npu_lat = payload.npu_latency_ms or 9.4
    igpu_lat = payload.igpu_latency_ms or 24.1
    cpu_lat = payload.cpu_latency_ms or 2.1
    tot_lat = round(npu_lat + igpu_lat + cpu_lat, 2)

    cycle_record = {
        "cycle_id": f"CYC-{brick_uuid}",
        "timestamp": time.strftime("%H:%M:%S"),
        "color": payload.color,
        "defect_label": payload.defect_label,
        "anomaly_score": payload.anomaly_score,
        "action": payload.action,
        "destination": "Bowl 1 (Accept)" if payload.action == "PERFECT_BOWL" else ("Bowl 2 (Defective)" if payload.action == "DEFECTIVE_BOWL" else "Inspection Turntable"),
        "root_cause_reasoning": payload.root_cause or "Edge telemetry processed via OpenVINO physical pipeline.",
        "raw_url": media_res.get("raw_url"),
        "heatmap_url": media_res.get("heatmap_url", media_res.get("composite_heatmap_url")),
        "composite_url": media_res.get("composite_heatmap_url"),
        "latencies": {
            "npu_anomalib_ms": npu_lat,
            "igpu_vla_ms": igpu_lat,
            "cpu_control_ms": cpu_lat,
            "total_ms": tot_lat,
        },
        "openvino_dispatch": {
            "anomalib": "NPU (OpenVINO NPU / 50 TOPS)",
            "vla_policy": "GPU.0 (12 Xe3 Cores)",
            "kinematics": "CPU (Intel TCC)",
        }
    }

    state.recent_cycles.insert(0, cycle_record)
    if len(state.recent_cycles) > 40:
        state.recent_cycles.pop()

    state.hardware_metrics["total_cycles_processed"] += 1
    state.hardware_metrics["total_pipeline_latency_ms"] = tot_lat
    if payload.action == "PERFECT_BOWL":
        state.hardware_metrics["perfect_count"] += 1
    elif payload.action == "DEFECTIVE_BOWL":
        state.hardware_metrics["defective_count"] += 1
    else:
        state.hardware_metrics["regrasp_count"] += 1

    await manager.broadcast({
        "type": "NEW_CYCLE",
        "cycle": cycle_record,
        "hardware_metrics": state.hardware_metrics,
    })

    return {"status": "success", "cycle_id": cycle_record["cycle_id"]}


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

    # Broadcast updated rules over WebSocket
    await manager.broadcast({
        "type": "RULE_CREATED",
        "rule": rule.model_dump(),
        "active_rules": [r.model_dump() for r in state.active_rules],
    })

    return {
        "status": "success",
        "rule": rule.model_dump(),
        "spoken_confirmation": rule.spoken_confirmation,
    }

@app.delete("/api/copilot/rule/{rule_id}")
async def delete_copilot_rule(rule_id: str):
    """
    Deletes an active sorting rule.
    """
    state.active_rules = [r for r in state.active_rules if r.rule_id != rule_id]
    await manager.broadcast({
        "type": "RULE_DELETED",
        "rule_id": rule_id,
        "active_rules": [r.model_dump() for r in state.active_rules],
    })
    return {"status": "success", "rule_id": rule_id}

@app.post("/mock-modal")
async def mock_modal_webhook(payload: Dict[str, Any]):
    """
    Mock endpoint simulating the Modal GPU training webhook (Slide 8).
    """
    logger.info(f"Received Modal training callback: {payload}")
    return {"status": "acknowledged", "job_id": f"modal-{uuid.uuid4()}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
