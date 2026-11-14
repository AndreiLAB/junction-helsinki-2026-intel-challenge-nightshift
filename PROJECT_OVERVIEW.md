# Project Overview: Autonomous Physical AI Inspection Cell (Junction 2026)

## 1. Event & Targeted Challenges

* **Event:** Junction 2026 (Helsinki/Espoo, Finland) — 48-hour hackathon.
* **Main Track — Intel Physical AI Challenge (100 pts):** Build an end-to-end closed-loop robotic defect inspection and sorting cell (`PERCEIVE -> DETECT -> REASON -> ACT -> OPTIMIZE`) using **Intel Physical AI Studio**, **Anomalib v2.7.0**, and **OpenVINO** on an **Intel Core Ultra X9 Series 3 (388H)** laptop.
  * *Scoring breakdown:* End-to-End Closed-Loop Solution (25 pts), Anomalib Defect Detection (20 pts), VLA & Physical AI Studio Integration (20 pts), OpenVINO & Core Ultra Series 3 Optimization (20 pts), Robotic Execution & Reliability including uncertainty recovery (10 pts), Innovation & Live Demo (5 pts).
* **Side Tracks Stacked on Top (Asynchronous Cloud Layer — Owned Here):**
  * **NVIDIA Nemotron (2× RTX 5080 prize):** `nemotron-3.5-super-vl` via Verda B300 endpoint (`https://containers.datacrunch.io/nemotron-3-5-super-vl-b300/v1`) acting as an asynchronous visual root-cause and threshold-tuning agent.
  * **Google Gemini API:** `gemini-3.8-flash` multimodal Floor Copilot (webcam + voice + structured JSON output) for hands-free operator rule commissioning and live spoken explanations.
  * **Best Use of Modal:** Official Modal GPU cloud training for VLA/Anomalib plus Modal serverless FastAPI webhooks and Sandboxes (`MODAL_WEBHOOK_URL`).
  * **MariaDB Challenge:** MariaDB 11.7+ storing cycle latency telemetry alongside native `VECTOR(512)` embeddings (`VEC_DISTANCE_COSINE`).
  * **Cloudinary Tech Challenge:** Programmatic uploads, chained `l_overlay` heatmap compositing, badges, and defect highlight trails (survey at `https://cld.media/hackathon-survey`).
  * **Supporting Assets:** **Qualia** (SO-ARM101 episode curation before training) and **IronShard** (>100 MiB model/dataset storage).

---

## 2. System Architecture & Station Hardware

![NightShift System Architecture — A closed loop. Not just a prediction.](docs/images/architecture.png)

* **Golden Architectural Rule:** The physical robot control loop stays **100% local** on the Intel Core Ultra X9 388H laptop via OpenVINO (<36 ms target loop). All cloud AI models (Gemini, Nemotron, Modal, MariaDB, Cloudinary) run **asynchronously off the critical path** so network latency never slows or breaks robot execution.
* **Physical Station Hardware (On Desk):**
  * **Laptop:** HP OmniBook Ultra (C2NM8AV) or Dell XPS 16 (DA16260) with **Intel Core Ultra X9 Series 3 (388H)**, 64 GB RAM, Ubuntu v26.04, pre-installed NPU/iGPU drivers (up to 180 platform TOPS).
  * **NPU (50 TOPS):** `Anomalib v2.7.0` (`EfficientAd`/`Padim`/`PatchCore`) defect scoring + heatmap.
  * **iGPU (12 Xe3 Cores):** Physical AI Studio VLA (`ACT` baseline + `SmolVLA`) with OpenVINO FP16 and async action chunking.
  * **CPU:** Deterministic control loop, safety action clamping, velocity limits, ROI preprocessing, and non-blocking event emission.
  * **Robot:** 1× **LeRobot SO-ARM101 Follower Arm** ("hand") + 1× **Leader Arm** ("controller").
  * **Cameras (2× Shared Rig):** `CAM-01` Top-View Workspace Camera (Duplo plate & bowls) + `CAM-02` Close-Up Inspection Camera (with plain paper backdrop for clean Anomalib ROI).
  * **Objects:** Plates with Lego Duplo blocks (normal vs. marker-defective) + two taped bowls labeled `GOOD` and `DEFECTIVE` (plus a sealed `EXAM` bag of 5 good + 5 defective bricks reserved for final testing).

---

## 3. Team Roles & Unified Cloud Hub Ownership

* **At the Physical Station (`~/duplo-cell` on Ubuntu):** 3 teammates run the physical robot station, Physical AI Studio recordings, `~/duplo-cell` Claude Code agents (`Lead`, `Policy`, `Inspection`, `Speed and demo`, `Robot`), and handle all station timekeeping, checkpoints, and screenshots.
* **In This Workspace (`f:/JunctionH 2026`) — Unified Cloud, AI & Data Hub Lead (Merged Member 3 + Member 4):**
  * **Zero timekeeping or physical table duties.** 100% focused on the unified asynchronous Cloud & Side-Track Backend + Mission Control Hub:
    1. **Google Gemini (`gemini-3.8-flash`):** Live multimodal Floor Copilot (`backend/gemini_copilot.py`).
    2. **Cloudinary (`l_overlay`):** Live inspection crop & heatmap upload + overlay compositing (`backend/cloudinary_media.py`).
    3. **NVIDIA Nemotron (`nemotron-3.5-super-vl` via Verda B300):** Async visual root-cause analysis and dynamic threshold tuning (`backend/nemotron_worker.py` -> `PATCH /api/cycles/{brick_uuid}/nemotron`).
    4. **MariaDB 11.7+ (`VECTOR(512)`):** Cycle telemetry persistence + `VEC_DISTANCE_COSINE` nearest-neighbor defect similarity search (`backend/mariadb_store.py`).
    5. **Modal Cloud Webhook (`MODAL_WEBHOOK_URL`):** Serverless escalation/audit webhook (`backend/modal_webhook.py`).
    6. **Zero-Dependency Station Bridge:** `backend/duplo_cell_bridge.py` & `backend/duplo_bridge_example.py` for non-blocking `POST /api/cycles` and `GET /api/policy` from `~/duplo-cell`.

---

## 4. Operating Rules for Antigravity (Dev One)

1. **Stay synced with [Redefine Dev One Role](conversation://f34354b2-6fed-417f-a2d2-788428256d40):** Check its transcript (`C:\Users\gagna\.gemini\antigravity\brain\f34354b2-6fed-417f-a2d2-788428256d40\.system_generated\logs\transcript.jsonl`) for any updated architectural or role instructions.
2. **Focus strictly on the Unified Cloud & AI Hub (M3 + M4):** Keep `backend/` and `frontend/` cleanly modular; preserve `POST /api/cycles`, `GET /api/policy`, and `PATCH /api/cycles/{brick_uuid}/nemotron` contracts. Do not add timekeeping clutter or touch local robot control code.
3. **Offline resilience:** Keep graceful fallbacks active in every cloud module (Gemini, Cloudinary, Nemotron Verda B300, MariaDB Vector, Modal) so the system works both with live credentials and offline.
4. **Never commit secrets:** Keep `backend/.env` and `.venv/` excluded via `.gitignore`.
5. **Verify before pushing:** Run `npm --prefix frontend run build` and backend integration tests before committing to `main`.
