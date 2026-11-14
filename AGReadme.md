# Unified Cloud, AI & Data Hub (M3 + M4) — 5/5 Live Cloud & Database Activation Log

## Live Cloud & Database Tracks (All 5/5 `LIVE`)
1. **Gemini 3.8 Flash Multimodal Copilot (`backend/gemini_copilot.py`):**
   - `GEMINI_MODEL = "gemini-3.8-flash"` via `google-genai` 3.3.0 structured `SortingRule` output (`LIVE`).
2. **Cloudinary Live Media & Overlay Pipeline (`backend/cloudinary_media.py`):**
   - Uploads raw inspection crops + heatmaps and generates `l_overlay` (`opacity: 45`) composite PNGs (`LIVE`).
3. **Verda B300 NVIDIA Nemotron 3.5 Super VL Worker (`backend/nemotron_worker.py`):**
   - Targets `https://containers.datacrunch.io/nemotron-3-5-super-vl-b300/v1` (`nemotron-3.5-super-vl`, `vllm-0.32.0`) over forced IPv4 (`local_address="0.0.0.0"`), inline 224×224 JPEG Data URIs, `chat_template_kwargs: {"enable_thinking": False}`, `max_tokens`, and `content` → `reasoning_content` / `reasoning` fallback (`LIVE`).
4. **MariaDB 11.8.2 LTS Native `VECTOR(512)` + `WITH SYSTEM VERSIONING` (`backend/mariadb_store.py`):**
   - Running locally on `127.0.0.1:3306` (`junction_ai`), also ready for hosted TLS `mysql://` / `mariadb://` URIs.
   - `inspection_cycles`: Native InnoDB `VECTOR(512)` + HNSW `VECTOR INDEX (embedding) M=8 DISTANCE=cosine` queried via `VEC_DISTANCE_COSINE(embedding, VEC_FromText(%s))` (`GET /api/cycles/{cycle_id}/similar`).
   - `sorting_policies`: MariaDB temporal `WITH SYSTEM VERSIONING` table tracking every Gemini Copilot rule mutation and Nemotron threshold calibration with microsecond validity ranges via `SELECT ... FOR SYSTEM_TIME ALL` (`GET /api/policies/history`).
5. **Modal Serverless Escalation Webhook (`backend/modal_webhook.py`):**
   - Deployed live at `https://gagnam609--junction2026-physical-ai-hub-escalation-audit-a13304.us-east.modal.run`.
   - Audits `DEFECTIVE_BOWL` / `REGRASP_TRIGGERED` cycles and persists defect manifests into `modal.Volume` (`junction-defect-archive`) and state counters into `modal.Dict` (`junction-escalation-state`) (`LIVE`).

## Verification Suite Results (2026-11-14)
- `GET /api/health`: All 5 providers (`gemini`, `cloudinary`, `nemotron`, `mariadb`, `modal`) verified `LIVE`.
- `GET /api/cycles/CYC-init_1/similar`: Verified `provider: "LIVE"` (`MariaDB 11.8 VECTOR(512) + SYSTEM VERSIONING`).
- `GET /api/policies/history`: Verified `provider: "LIVE"` (`MariaDB WITH SYSTEM VERSIONING (FOR SYSTEM_TIME ALL)`).
- `python backend/test_live_stream.py`: 100% PASS (5/5 steps).
- `npm --prefix frontend run build`: 0 errors (`dist/` built cleanly).
