# 🏭 Junction Helsinki 2026 — Intel Physical AI Challenge
## Team NightShift | Autonomous Duplo Brick Robotic Inspection Cell
> **Lead Author:** Unified Cloud, AI & Data Hub Lead (Merged Member 3 + Member 4) — *Gemini 3.8 Copilot, Verda B300 Nemotron, MariaDB Vector Store, Modal Escalation, Cloudinary Media & Mission Control UI*

---

## 🧭 Executive Summary (Unified Cloud, AI & Data Hub)

This repository implements **Team NightShift's Unified Cloud, AI & Data Hub** — decoupling all heavy multimodal reasoning, vector similarity indexing, media compositing, and live telemetry visualization from the `<36 ms` local robot loop on the Ubuntu Intel Core Ultra X9 388H workstation (`~/duplo-cell`).

Built in **Python FastAPI** and **React + Vite + Tailwind CSS**, the hub delivers:
1. **Real-Time Closed-Loop Telemetry (`PERCEIVE → DETECT → REASON → ACT → OPTIMIZE`)** across Intel Core Ultra X9 388H heterogeneous silicon:
   - **50-TOPS NPU:** Anomalib v2.7.0 PatchCore defect localization (~9.4 ms, 4.8W sustained).
   - **12 Xe3 Cores (iGPU):** SmolVLA / ACT task planning via OpenVINO (~24.1 ms, 41.5 FPS).
   - **Deterministic CPU:** Intel TCC + TSN real-time kinematics loop (~2.1 ms, jitter <15µs).
   - **Total edge decision loop: ~35.6 ms (28+ Hz throughput)** with **0 ms** added cloud latency.
2. **Gemini 3.8 Flash Hands-Free Floor Copilot (`backend/gemini_copilot.py`):** Operators show a marked brick coupon to the webcam and speak a rule in plain English, updating active sorting rules (`GET /api/policy`) with spoken audio confirmation.
3. **Cloudinary Visual Audit Trail (`backend/cloudinary_media.py`):** Uploads raw inspection crops and Anomalib heatmaps, auto-compositing semi-transparent `l_overlay` (`opacity: 45`) layers.
4. **Verda B300 NVIDIA Nemotron 3.5 Super VL Worker (`backend/nemotron_worker.py`):** Asynchronous background visual root-cause reasoning and dynamic anomaly threshold auto-tuning streamed live via `CYCLE_UPDATED` WebSocket events.
5. **MariaDB 11.7+ `VECTOR(512)` Defect Store (`backend/mariadb_store.py`):** Indexes 512-dim visual + telemetry brick embeddings (`VEC_DISTANCE_COSINE`) to surface top-3 historical defect twins on every cycle (`GET /api/cycles/{id}/similar`), with automatic in-memory cosine fallback.
6. **Modal Serverless Escalation Webhook (`backend/modal_webhook.py`):** Deployable `@modal.fastapi_endpoint` (`modal deploy backend/modal_webhook.py`) triggered asynchronously on `DEFECTIVE_BOWL` and `REGRASP_TRIGGERED` cycles for batch audit & retraining hooks.

---

## 🏛 System Architecture

```
                                +------------------------------------------+
                                |         Gemini 3.8 Flash Copilot         |
                                |  (Webcam + Voice Hands-Free Commission)  |
                                +--------------------+---------------------+
                                                     | POST /api/copilot/rule
                                                     v
+--------------------------+        +--------------------+        +-------------------------+
| CAM-01: Top-View (D415)  | -----> |  FastAPI Edge Hub  | <----- | LeRobot SO-ARM101       |
| CAM-02: Wrist Crop (QHD) |        |   (Port 8000)      |        | Follower Manipulation   |
+--------------------------+        +---------+----------+        +-------------------------+
                                              |
                   +--------------------------+--------------------------+
                   |                          |                          |
                   v                          v                          v
          [NPU: 50 TOPS]             [iGPU: 12 Xe3 Cores]        [CPU: Deterministic]
        Anomalib v2.7.0                SmolVLA / ACT Policy        Intel TCC + TSN Loop
        PatchCore (~9.4ms)                (~24.1ms)                     (~2.1ms)
                   \                          |                          /
                    +-------------------------+-------------------------+
                                              |
                                              v
                              +-------------------------------+
                              |   Total Latency: ~35.6 ms     |
                              |   Full Closed-Loop (28+ Hz)   |
                              +---------------+---------------+
                                              |
                             +----------------+----------------+
                             |                                 |
                             v                                 v
                +--------------------------+     +--------------------------+
                | Cloudinary Visual Trail  |     | Mission Control UI       |
                | (Auto Layer Overlays)    |     | (Vite + React Obsidian)  |
                +--------------------------+     +--------------------------+
```

---

## 🖥 The 5 Dashboard Panels (Figma Make & SCADA Design)

The dashboard is engineered in an **obsidian industrial dark-mode** design system specifically proportioned for 16:9 laptop screens (`1440×900`) with zero numeric jitter (`tabular-nums`):

| Panel | Description | Key Technologies |
|---|---|---|
| **1. Closed-Loop Pipeline Bar** | Highlights the active stage in real time (`PERCEIVE → DETECT → REASON → ACT → OPTIMIZE`) with animated progress glow and hardware dispatch tags. | React, WebSockets, OpenVINO profiling |
| **2. Dual-Camera & Heatmap Feed** | Overhead arena map (`CAM-01 Top-View Workspace`) with SO-ARM101 trajectory simulation + close-up inspection (`CAM-02 Anomalib v2.7.0`) with toggleable **Overlay**, **Heatmap**, and **Raw** modes, plus non-wrapping 0.55 decision gauge. | SVG, Cloudinary, Anomalib PatchCore |
| **3. Intel Core Ultra X9 Telemetry** | Real-time latency & power cards for **50-TOPS NPU**, **12 Xe3 Cores**, and **CPU**, complete with offline pitch buttons (`Simulate Perfect`, `Simulate Defect`, `Simulate Re-grasp`, and continuous `Auto-Cycle Pitch Mode`). | Intel TCC/TSN, OpenVINO Heterogeneous |
| **4. Gemini Multimodal Floor Copilot** | Hands-free operator commissioning tool: laptop webcam snapshot + microphone recording + text prompt chips. Returns structured Pydantic sorting rules and confirms aloud using `window.speechSynthesis`. | `gemini-3.8-flash`, WebRTC, SpeechSynthesis |
| **5. Nemotron Audit & Root-Cause** | Scrollable audit feed of inspected bricks with Cloudinary composite thumbnails, anomaly scores, bin routing, and Nemotron physical root-cause analysis. Clicking any entry opens a 3-way high-res comparison modal. | Cloudinary API, Nemotron / LLM Reasoning |

---

## ⚡ Quick Start Guide

### 1. Prerequisites
- **Python 3.11 - 3.14**
- **Node.js v20+** and **npm**

### 2. Backend Setup (`./backend`)
```bash
cd backend

# Create & activate virtual environment (Windows PowerShell)
python -m venv .venv
.\.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start FastAPI hub with WebSocket streaming
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
* Interactive Swagger Docs: **http://localhost:8000/docs**
* Health Endpoint: **http://localhost:8000/api/health**
* WebSocket Stream: **ws://localhost:8000/ws/live**

### 3. Frontend Setup (`./frontend`)
```bash
cd frontend

# Install packages
npm install

# Start Vite dev server
npm run dev
```
* Mission Control Dashboard: **http://localhost:5173**

---

## 🔑 Environment Configuration (`backend/.env`)

```env
# Google AI Studio API Key for Gemini 3.8 Flash Multimodal Copilot
GEMINI_API_KEY=your_gemini_api_key_here

# Cloudinary URL for media asset uploads & composite overlays
CLOUDINARY_URL=cloudinary://api_key:api_secret@cloud_name

# Verda Cloud B300 NVIDIA Nemotron 3.5 Super VL
NEMOTRON_BASE_URL=https://containers.datacrunch.io/nemotron-3-5-super-vl-b300/v1
NEMOTRON_API_KEY=your_verda_api_key_here
NEMOTRON_MODEL=nemotron-3.5-super-vl

# MariaDB 11.7+ Native Vector Search (VECTOR(512) + VEC_DISTANCE_COSINE)
MARIADB_URI=mysql://user:password@host:3306/junction_ai

# Modal Serverless Escalation Webhook (`modal deploy backend/modal_webhook.py`)
MODAL_WEBHOOK_URL=http://localhost:8000/mock-modal

PORT=8000
HOST=0.0.0.0
```

> [!TIP]
> **Honest Live vs. Fallback Telemetry:** `GET /api/health` exposes live connectivity status (`LIVE` vs `FALLBACK`) for all 5 cloud providers (`Gemini 3.8`, `Cloudinary`, `Nemotron B300`, `MariaDB Vector`, and `Modal`). Any unconfigured or offline service falls back cleanly in-process with zero errors.

---

## 🤝 Edge Workstation Integration (`~/duplo-cell` → Cloud Hub)

Copy `backend/duplo_cell_bridge.py` to the Ubuntu Intel Core Ultra X9 388H workstation (`~/duplo-cell`) or call `POST /api/cycles` directly. `push_cycle_async` dispatches on a daemon thread so the physical SO-ARM101 loop never blocks (`0 ms` added latency):

```python
from duplo_cell_bridge import push_cycle_async, get_active_policy

# 1. Poll active Gemini sorting rules & Nemotron-tuned anomaly threshold
policy = get_active_policy(hub_url="http://<CLOUD_HUB_LAN_IP>:8000")

# 2. Fire-and-forget cycle push after each brick inspection
push_cycle_async(
    color="yellow",
    defect_label="Marker Stripe Contamination",
    anomaly_score=0.78,
    action="DEFECTIVE_BOWL",
    raw_image_path="/tmp/cam02_raw.png",
    heatmap_image_path="/tmp/cam02_heatmap.png",
    npu_latency_ms=9.4,
    igpu_latency_ms=24.1,
    cpu_latency_ms=2.1,
    hub_url="http://<CLOUD_HUB_LAN_IP>:8000",
)
```

---

## 🎤 3-Minute Live Pitch Script for Judges

1. **The Hook (30s):**
   > *"Welcome to Team NightShift's Autonomous Physical AI Inspection Cell. Traditional factory inspection stops at classification—our cell perceives defects, reasons with vision-language-action policies, and physically sorts acceptable and defective Duplo blocks using a closed loop on Intel Core Ultra Series 3."*
2. **The Intel Hardware Story (60s):**
   > *"Notice our hardware telemetry panel. We mapped each workload to what Intel silicon does best: Anomalib v2.7.0 runs on the 50-TOPS NPU in 9.4ms consuming only 4.8W. SmolVLA runs on the 12 Xe3 iGPU cores in 24.1ms. Our deterministic kinematics loop runs on the CPU with Intel TCC/TSN in 2.1ms. That's a total decision cycle of ~35.6ms—enabling 28 Hz real-time manipulation without cloud latency."*
3. **The Gemini Multimodal Copilot (60s):**
   > *(Click the microphone or prompt chip: "Reject yellow bricks with black side stripes")*
   > *"Watch our Gemini 3.8 Flash copilot. An operator can hold a marked coupon to the camera and speak in plain English. Gemini extracts a structured policy rule, deploys it to our robot state machine in milliseconds, and speaks voice confirmation aloud."*
4. **Visual Audit Trail & Root-Cause (30s):**
   > *(Click any cycle in the audit feed to open the 3-way modal)*
   > *"Every single cycle is indexed with Cloudinary semi-transparent heatmap overlays and Nemotron root-cause analysis, giving factory managers a complete visual audit trail."*
