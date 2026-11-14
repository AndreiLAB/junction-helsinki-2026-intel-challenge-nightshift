"""
Modal Serverless Escalation Audit Webhook & Async Client Dispatcher.

Dual-purpose module for the Junction 2026 Physical AI Inspection Hub:
1. Deployable Modal serverless FastAPI endpoint (`modal deploy backend/modal_webhook.py`)
   that audits escalated `DEFECTIVE_BOWL` / `REGRASP_TRIGGERED` cycles and persists
   structured defect manifests into a `modal.Volume` (`junction-defect-archive`) and
   live state counters into a `modal.Dict` (`junction-escalation-state`).
2. Local non-blocking client helper imported by `backend/main.py` (`dispatch_modal_escalation`,
   `get_modal_status`) that works seamlessly even when `modal` is not imported by `main.py`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import time
import urllib.parse
import urllib.request
import uuid
from typing import Any, Optional

try:
    from dotenv import dotenv_values, load_dotenv
except ImportError:  # pragma: no cover - serverless container image
    dotenv_values = None  # type: ignore[assignment]
    load_dotenv = None  # type: ignore[assignment]

try:
    import modal
except ImportError:
    modal = None  # type: ignore[assignment]

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore[assignment]

_DOTENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
if load_dotenv is not None:
    load_dotenv(dotenv_path=_DOTENV_PATH, override=False)

logger = logging.getLogger("modal_webhook")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

DEFAULT_MODAL_WEBHOOK_URL = "http://localhost:8000/mock-modal"
TARGET_TRAINING_BRANCH = "physical-ai-studio/junction2026"
RETRAIN_ANOMALY_SCORE_THRESHOLD = 0.85

_INIT_ENV_WEBHOOK_URL = os.environ.get("MODAL_WEBHOOK_URL")
MODAL_WEBHOOK_URL: str = (
    (_INIT_ENV_WEBHOOK_URL or "").strip() or DEFAULT_MODAL_WEBHOOK_URL
)
_INIT_WEBHOOK_URL = MODAL_WEBHOOK_URL

_last_remote_ok: Optional[bool] = None

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "::1"})
_PLACEHOLDER_MARKERS = (
    "your_modal_url_here",
    "your_modal_webhook_here",
    "your_webhook_url_here",
    "<modal",
    "placeholder",
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else default
    except (TypeError, ValueError):
        return default


def _get_webhook_url() -> str:
    """Resolve active MODAL_WEBHOOK_URL honoring runtime attribute or live .env updates."""
    if MODAL_WEBHOOK_URL != _INIT_WEBHOOK_URL:
        return (MODAL_WEBHOOK_URL or "").strip() or DEFAULT_MODAL_WEBHOOK_URL
    current_env = os.environ.get("MODAL_WEBHOOK_URL")
    if current_env != _INIT_ENV_WEBHOOK_URL and current_env is not None:
        return current_env.strip() or DEFAULT_MODAL_WEBHOOK_URL
    if dotenv_values is not None and os.path.isfile(_DOTENV_PATH):
        try:
            cfg = dotenv_values(_DOTENV_PATH)
            file_url = (cfg.get("MODAL_WEBHOOK_URL") or "").strip()
            if file_url:
                return file_url
        except Exception:
            pass
    return (MODAL_WEBHOOK_URL or "").strip() or DEFAULT_MODAL_WEBHOOK_URL


def _is_remote_modal_url(url: str) -> bool:
    if not isinstance(url, str):
        return False

    cleaned = url.strip()
    if not cleaned or any(ch.isspace() for ch in cleaned):
        return False

    lowered = cleaned.lower()
    if any(marker in lowered for marker in _PLACEHOLDER_MARKERS):
        return False
    if "/mock-modal" in lowered:
        return False

    try:
        parsed = urllib.parse.urlparse(cleaned)
    except ValueError:
        return False

    if parsed.scheme.lower() not in {"https", "http"}:
        return False

    host = (parsed.hostname or "").strip().lower()
    if not host or host in _LOCAL_HOSTS or host.endswith(".localhost"):
        return False

    if "." not in host and ":" not in host:
        return False

    path = (parsed.path or "").lower()
    if "/mock-modal" in path:
        return False

    return True


def _should_recommend_retrain(action: str, anomaly_score: float) -> bool:
    normalized_action = (action or "").strip().upper()
    return (
        normalized_action in {"REGRASP_TRIGGERED", "REGRASP_AND_RECHECK"}
        or anomaly_score > RETRAIN_ANOMALY_SCORE_THRESHOLD
    )


def evaluate_escalation_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Core audit logic shared by the deployed Modal FastAPI endpoint and local callers.
    """
    data = payload if isinstance(payload, dict) else {}

    cycle_id = str(data.get("cycle_id") or f"CYC-{uuid.uuid4().hex[:8]}")
    color = str(data.get("color") or "unknown")
    defect_label = str(data.get("defect_label") or "Unspecified Anomaly")
    anomaly_score = round(_safe_float(data.get("anomaly_score"), 0.0), 4)
    action = str(data.get("action") or "DEFECTIVE_BOWL")

    raw_latencies = data.get("latencies")
    latencies = raw_latencies if isinstance(raw_latencies, dict) else {}
    total_ms = _safe_float(
        latencies.get("total_ms", latencies.get("npu_anomalib_ms")),
        0.0,
    )
    latency_tag = f"{total_ms:.1f} ms loop" if total_ms > 0 else "edge telemetry"

    retrain_recommended = _should_recommend_retrain(action, anomaly_score)
    uuid4_short = uuid.uuid4().hex[:8]

    action_upper = action.strip().upper()
    if action_upper in {"REGRASP_TRIGGERED", "REGRASP_AND_RECHECK"}:
        audit_note = (
            f"Boundary uncertainty ({anomaly_score:.3f}) on {color} brick "
            f"('{defect_label}'); queued active-learning episode for SmolVLA/PatchCore "
            f"calibration ({latency_tag})."
        )
    elif anomaly_score > RETRAIN_ANOMALY_SCORE_THRESHOLD:
        audit_note = (
            f"High-severity anomaly ({anomaly_score:.3f} > {RETRAIN_ANOMALY_SCORE_THRESHOLD:.2f}) "
            f"on {color} brick ('{defect_label}'); flagged out-of-distribution drift for "
            f"Anomalib PatchCore retraining ({latency_tag})."
        )
    else:
        audit_note = (
            f"Recorded escalated {action} event ({anomaly_score:.3f}) on {color} brick "
            f"('{defect_label}'); within current PatchCore calibration envelope ({latency_tag})."
        )

    return {
        "status": "escalated",
        "provider": "modal_serverless",
        "job_id": f"modal-{uuid4_short}",
        "cycle_id": cycle_id,
        "retrain_recommended": bool(retrain_recommended),
        "target_branch": TARGET_TRAINING_BRANCH,
        "audit_note": audit_note,
    }


# ---------------------------------------------------------------------------
# 1. Deployable Modal Serverless FastAPI Endpoint (`modal deploy backend/modal_webhook.py`)
# ---------------------------------------------------------------------------
if modal is not None:
    image = modal.Image.debian_slim(python_version="3.12").pip_install(
        "fastapi[standard]",
        "pydantic",
    )
    defect_volume = modal.Volume.from_name(
        "junction-defect-archive", create_if_missing=True
    )
    escalation_state = modal.Dict.from_name(
        "junction-escalation-state", create_if_missing=True
    )
    app = modal.App("junction2026-physical-ai-hub", image=image)

    @app.function(volumes={"/archive": defect_volume})
    @modal.fastapi_endpoint(method="POST")
    def escalation_audit_webhook(payload: dict) -> dict:
        """
        Serverless Modal webhook auditing escalated inspection cycles and persisting
        defect manifests into `modal.Volume` (`junction-defect-archive`) and
        state telemetry into `modal.Dict` (`junction-escalation-state`).
        """
        result = evaluate_escalation_payload(payload)
        safe_cycle_id = "".join(
            ch if (ch.isalnum() or ch in ("-", "_")) else "_"
            for ch in str(result["cycle_id"])
        )[:64]
        manifest_rel_path = f"/archive/{safe_cycle_id}_{result['job_id']}.json"
        manifest = {
            **result,
            "persisted_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "color": str((payload or {}).get("color") or "unknown"),
            "defect_label": str((payload or {}).get("defect_label") or "Unspecified"),
            "anomaly_score": _safe_float((payload or {}).get("anomaly_score"), 0.0),
            "action": str((payload or {}).get("action") or "DEFECTIVE_BOWL"),
            "composite_url": (payload or {}).get("composite_url"),
            "latencies": (payload or {}).get("latencies") or {},
        }

        try:
            os.makedirs("/archive", exist_ok=True)
            with open(manifest_rel_path, "w", encoding="utf-8") as mf:
                json.dump(manifest, mf, indent=2)
            with open("/archive/escalations.jsonl", "a", encoding="utf-8") as jf:
                jf.write(json.dumps(manifest) + "\n")
            defect_volume.commit()
            result["archive_path"] = manifest_rel_path
        except Exception as vol_exc:
            result["archive_error"] = type(vol_exc).__name__

        try:
            prev_total = int(escalation_state.get("total_escalations", 0) or 0)
            new_total = prev_total + 1
            escalation_state["total_escalations"] = new_total
            escalation_state[str(result["cycle_id"])] = manifest
            if result.get("retrain_recommended"):
                prev_retrain = int(escalation_state.get("retrain_flagged", 0) or 0)
                escalation_state["retrain_flagged"] = prev_retrain + 1
            result["total_escalations"] = new_total
        except Exception as dict_exc:
            result["state_error"] = type(dict_exc).__name__

        return result

else:
    image = None
    defect_volume = None
    escalation_state = None
    app = None

    def escalation_audit_webhook(payload: dict) -> dict:
        """Local callable equivalent when the `modal` package is not installed."""
        return evaluate_escalation_payload(payload)


# ---------------------------------------------------------------------------
# 2. Local Async Client Dispatcher & Health Status (for `backend/main.py`)
# ---------------------------------------------------------------------------
def _build_dispatch_payload(cycle: dict[str, Any]) -> dict[str, Any]:
    data = cycle if isinstance(cycle, dict) else {}

    raw_latencies = data.get("latencies")
    latencies: dict[str, Any] = dict(raw_latencies) if isinstance(raw_latencies, dict) else {}

    comp_val = data.get("composite_url")
    if isinstance(comp_val, str):
        composite_url: Optional[str] = (
            f"{comp_val[:30]}...[inline-{len(comp_val)}-chars]"
            if comp_val.startswith("data:") and len(comp_val) > 512
            else comp_val
        )
    else:
        composite_url = None

    return {
        "cycle_id": str(data.get("cycle_id") or f"CYC-{uuid.uuid4().hex[:8]}"),
        "timestamp": str(data.get("timestamp") or time.strftime("%H:%M:%S")),
        "color": str(data.get("color") or "unknown"),
        "defect_label": str(data.get("defect_label") or "Unspecified Anomaly"),
        "anomaly_score": round(_safe_float(data.get("anomaly_score"), 0.0), 4),
        "action": str(data.get("action") or "DEFECTIVE_BOWL"),
        "composite_url": composite_url,
        "latencies": latencies,
    }


async def _post_webhook_json(
    url: str, payload: dict[str, Any], is_remote: bool = False
) -> tuple[int, dict[str, Any]]:
    if httpx is not None:
        transport = (
            httpx.AsyncHTTPTransport(local_address="0.0.0.0") if is_remote else None
        )
        async with httpx.AsyncClient(timeout=10.0, transport=transport) as client:
            response = await client.post(url, json=payload)
            status_code = int(response.status_code)
            try:
                parsed = response.json()
                body = parsed if isinstance(parsed, dict) else {}
            except Exception:
                body = {}
            return status_code, body

    if requests is not None:
        def _sync_requests_post() -> tuple[int, dict[str, Any]]:
            resp = requests.post(url, json=payload, timeout=10.0)
            code = int(resp.status_code)
            try:
                parsed = resp.json()
                return code, (parsed if isinstance(parsed, dict) else {})
            except Exception:
                return code, {}

        return await asyncio.to_thread(_sync_requests_post)

    def _sync_urllib_post() -> tuple[int, dict[str, Any]]:
        encoded = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=encoded,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            code = int(getattr(resp, "status", 200))
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
                return code, (parsed if isinstance(parsed, dict) else {})
            except Exception:
                return code, {}

    return await asyncio.to_thread(_sync_urllib_post)


async def dispatch_modal_escalation(cycle: dict) -> dict:
    """
    Asynchronously escalate a `DEFECTIVE_BOWL` or `REGRASP_TRIGGERED` cycle to
    `MODAL_WEBHOOK_URL` (Modal serverless endpoint or local `/mock-modal` stub).
    """
    global _last_remote_ok

    payload = _build_dispatch_payload(cycle)
    default_retrain = _should_recommend_retrain(
        payload["action"],
        payload["anomaly_score"],
    )

    target_url = _get_webhook_url()
    is_remote = _is_remote_modal_url(target_url)

    try:
        status_code, resp_data = await _post_webhook_json(
            target_url, payload, is_remote=is_remote
        )

        if 200 <= status_code < 300:
            if is_remote:
                _last_remote_ok = True

            raw_job_id = resp_data.get("job_id")
            job_id = (
                str(raw_job_id).strip()
                if raw_job_id
                else f"modal-{uuid.uuid4().hex[:8]}"
            )
            retrain_recommended = (
                bool(resp_data["retrain_recommended"])
                if "retrain_recommended" in resp_data
                and resp_data["retrain_recommended"] is not None
                else default_retrain
            )
            result = {
                "dispatched": True,
                "provider": "modal_cloud" if is_remote else "mock_local",
                "job_id": job_id,
                "retrain_recommended": retrain_recommended,
            }
            if resp_data.get("archive_path"):
                result["archive_path"] = str(resp_data["archive_path"])
            if resp_data.get("total_escalations") is not None:
                result["total_escalations"] = int(resp_data["total_escalations"])
            return result

        if is_remote:
            _last_remote_ok = False
        logger.warning(
            "Modal escalation webhook returned HTTP %d; using local fallback.",
            status_code,
        )
    except Exception as e:
        if is_remote:
            _last_remote_ok = False
        logger.warning(
            "Modal escalation dispatch failed (%s); using local fallback.",
            type(e).__name__,
        )

    return {
        "dispatched": False,
        "provider": "fallback",
        "job_id": f"modal-fallback-{uuid.uuid4().hex[:8]}",
        "retrain_recommended": default_retrain,
    }


def get_modal_status() -> dict:
    target_url = _get_webhook_url()
    is_remote = _is_remote_modal_url(target_url)

    if is_remote and _last_remote_ok is not False:
        return {
            "configured": True,
            "live": True,
            "mode": "LIVE",
            "detail": "Modal Serverless (Volume + Dict)",
        }

    if _last_remote_ok is False:
        return {
            "configured": is_remote,
            "live": False,
            "mode": "FALLBACK",
            "detail": "Modal endpoint unreachable · fallback",
        }

    return {
        "configured": False,
        "live": False,
        "mode": "FALLBACK",
        "detail": "Local /mock-modal stub",
    }


__all__ = [
    "MODAL_WEBHOOK_URL",
    "app",
    "image",
    "defect_volume",
    "escalation_state",
    "escalation_audit_webhook",
    "evaluate_escalation_payload",
    "dispatch_modal_escalation",
    "get_modal_status",
    "_is_remote_modal_url",
]
