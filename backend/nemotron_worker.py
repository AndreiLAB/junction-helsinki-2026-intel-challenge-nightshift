"""
Verda B300 Cloud Worker — NVIDIA Nemotron 3.5 Super VL Integration.

Provides asynchronous post-cycle multimodal root-cause auditing and dynamic
Anomalib threshold calibration against an OpenAI-compatible Verda B300 endpoint,
with zero-downtime deterministic engineering fallback and honest health reporting.
"""

import asyncio
import json
import logging
import math
import os
import re
from typing import Any, Optional

from dotenv import load_dotenv

try:
    import httpx
except ImportError:  # pragma: no cover - graceful fallback if httpx not yet installed
    httpx = None  # type: ignore[assignment]

# Resolve backend configuration independently of the process working directory.
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"), override=False)

logger = logging.getLogger("nemotron_worker")
# Prevent HTTP client libraries from echoing full endpoint URLs at INFO level.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

DEFAULT_NEMOTRON_BASE_URL = "https://containers.datacrunch.io/nemotron-3-5-super-vl-b300/v1"
DEFAULT_NEMOTRON_MODEL = "nemotron-3.5-super-vl"

_PLACEHOLDER_API_KEYS = frozenset(
    {
        "your_nemotron_key_here",
        "your_nemotron_api_key_here",
        "your_api_key_here",
    }
)


def _clean_api_key(raw: Optional[str]) -> str:
    """Strip whitespace and treat placeholder values as empty."""
    if not raw:
        return ""
    cleaned = raw.strip()
    if not cleaned or cleaned.lower() in _PLACEHOLDER_API_KEYS:
        return ""
    return cleaned


_INIT_ENV_BASE_URL = os.environ.get("NEMOTRON_BASE_URL")
_INIT_ENV_MODEL = os.environ.get("NEMOTRON_MODEL")
_INIT_ENV_API_KEY = os.environ.get("NEMOTRON_API_KEY")

NEMOTRON_BASE_URL: str = (
    os.environ.get("NEMOTRON_BASE_URL", "").strip() or DEFAULT_NEMOTRON_BASE_URL
)
NEMOTRON_MODEL: str = (
    os.environ.get("NEMOTRON_MODEL", "").strip() or DEFAULT_NEMOTRON_MODEL
)
NEMOTRON_API_KEY: str = _clean_api_key(_INIT_ENV_API_KEY)

_INIT_BASE_URL = NEMOTRON_BASE_URL
_INIT_MODEL = NEMOTRON_MODEL
_INIT_API_KEY = NEMOTRON_API_KEY

# Tri-state connectivity tracker:
#   None  -> no cycle analyzed yet since process start
#   True  -> most recent Verda B300 call succeeded
#   False -> most recent Verda B300 call failed / fell back
_last_call_live: Optional[bool] = None

__all__ = [
    "NEMOTRON_BASE_URL",
    "NEMOTRON_MODEL",
    "NEMOTRON_API_KEY",
    "analyze_cycle_with_nemotron",
    "get_nemotron_status",
]


def _get_config() -> tuple[str, str, str]:
    """Return active (base_url, model, api_key), honoring runtime or env overrides."""
    if NEMOTRON_BASE_URL != _INIT_BASE_URL:
        base_url = (NEMOTRON_BASE_URL or "").strip()
    elif os.environ.get("NEMOTRON_BASE_URL") != _INIT_ENV_BASE_URL:
        env_url = os.environ.get("NEMOTRON_BASE_URL")
        base_url = env_url.strip() if env_url is not None else DEFAULT_NEMOTRON_BASE_URL
    else:
        base_url = (NEMOTRON_BASE_URL or "").strip()

    if NEMOTRON_MODEL != _INIT_MODEL:
        model = (NEMOTRON_MODEL or "").strip() or DEFAULT_NEMOTRON_MODEL
    elif os.environ.get("NEMOTRON_MODEL") != _INIT_ENV_MODEL:
        model = (os.environ.get("NEMOTRON_MODEL") or "").strip() or DEFAULT_NEMOTRON_MODEL
    else:
        model = (NEMOTRON_MODEL or "").strip() or DEFAULT_NEMOTRON_MODEL

    if NEMOTRON_API_KEY != _INIT_API_KEY:
        api_key = _clean_api_key(NEMOTRON_API_KEY)
    elif os.environ.get("NEMOTRON_API_KEY") != _INIT_ENV_API_KEY:
        api_key = _clean_api_key(os.environ.get("NEMOTRON_API_KEY"))
    else:
        api_key = _clean_api_key(NEMOTRON_API_KEY)

    return base_url, model, api_key


def _extract_image_url(cycle: dict[str, Any]) -> Optional[str]:
    """Select composite heatmap URL/data-URI first, falling back to raw inspection URL."""
    for key in ("composite_url", "raw_url"):
        val = cycle.get(key)
        if isinstance(val, str):
            trimmed = val.strip()
            if trimmed.startswith(("http://", "https://", "data:")):
                return trimmed
    return None


def _normalize_threshold(raw_val: Any) -> Optional[float]:
    """Validate suggested_threshold as None or a finite float clamped to [0.40, 0.75]."""
    if raw_val is None or isinstance(raw_val, bool):
        return None
    if isinstance(raw_val, str):
        stripped = raw_val.strip().lower()
        if not stripped or stripped == "null" or stripped == "none":
            return None
    try:
        numeric = float(raw_val)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    clamped = min(0.75, max(0.40, numeric))
    return round(clamped, 4)


def _parse_completion_json(response_text: str) -> tuple[str, Optional[float]]:
    """Extract and validate root_cause and suggested_threshold from chat completion JSON."""
    envelope = json.loads(response_text)
    if not isinstance(envelope, dict):
        raise ValueError("Completion payload is not a JSON object")

    choices = envelope.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("Completion payload missing choices")

    first_choice = choices[0] if isinstance(choices[0], dict) else {}
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise ValueError("Completion choice missing message")

    content = message.get("content")
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Completion message content is empty")

    # Strip optional reasoning blocks (<think>...</think>) and markdown fences.
    cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    fence_match = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        cleaned,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if fence_match:
        json_str = fence_match.group(1)
    else:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            json_str = cleaned[start : end + 1]
        else:
            json_str = cleaned

    parsed = json.loads(json_str)
    if not isinstance(parsed, dict):
        raise ValueError("Model output JSON is not an object")

    root_cause = parsed.get("root_cause")
    if not isinstance(root_cause, str) or not root_cause.strip():
        raise ValueError("Model output missing non-empty root_cause")

    suggested_threshold = _normalize_threshold(parsed.get("suggested_threshold"))
    return root_cause.strip(), suggested_threshold


def _heuristic_fallback_analysis(cycle: dict[str, Any]) -> dict[str, Any]:
    """
    Deterministic physical manufacturing root-cause generator tailored to cycle telemetry.
    Guarantees reliable inspection insights when Verda B300 is unreachable or unconfigured.
    """
    color = str(cycle.get("color") or "polymer").strip().lower()
    defect_label = str(cycle.get("defect_label") or "Unspecified surface variance").strip()
    action = str(cycle.get("action") or "INSPECT").strip().upper()
    try:
        score = float(cycle.get("anomaly_score", 0.0))
    except (TypeError, ValueError):
        score = 0.0

    defect_lower = defect_label.lower()
    suggested_threshold: Optional[float] = None

    if (
        "REGRASP" in action
        or "glare" in defect_lower
        or "reflection" in defect_lower
        or "ambiguous" in defect_lower
    ):
        suggested_threshold = 0.53
        root_cause = (
            f"High-gloss {color} ABS bevel geometry produced localized specular glare "
            f"({defect_label}, PatchCore score {score:.2f}) near the decision boundary; "
            f"wrist re-grasp alters incident camera illumination while calibrating threshold to 0.53."
        )
    elif action == "PERFECT_BOWL" or (
        ("pristine" in defect_lower or defect_lower.startswith("none")) and score < 0.40
    ):
        root_cause = (
            f"Injection-molded {color} ABS brick exhibits uniform stud concentricity and "
            f"zero topological deviation (PatchCore score {score:.2f}); cleared for GOOD bowl routing."
        )
    elif "scratch" in defect_lower or "groove" in defect_lower:
        root_cause = (
            f"Linear mechanical abrasion along {color} brick sidewall ({defect_label}, score {score:.2f}) "
            f"indicates feeder rail friction or post-ejection scuffing; diverted to DEFECTIVE bowl."
        )
    elif "crack" in defect_lower or "stud" in defect_lower or "fracture" in defect_lower:
        root_cause = (
            f"Structural micro-fissure on {color} top stud boss ({defect_label}, score {score:.2f}) "
            f"consistent with mold ejection pin stress or weld-line weakness; rejected to protect clutch fit."
        )
    elif "stripe" in defect_lower or "marker" in defect_lower or "contamination" in defect_lower:
        root_cause = (
            f"High-contrast pigment streak on {color} polymer wall ({defect_label}, score {score:.2f}) "
            f"traced to colorant purge residue or QA test marking; isolated in DEFECTIVE bowl."
        )
    elif "chip" in defect_lower or "corner" in defect_lower:
        root_cause = (
            f"Localized perimeter spalling on {color} brick corner ({defect_label}, score {score:.2f}) "
            f"from vibratory feeder impact or cavity short-shot; routed to DEFECTIVE bowl."
        )
    else:
        if 0.44 <= score <= 0.58 and action != "DEFECTIVE_BOWL":
            suggested_threshold = 0.53
        root_cause = (
            f"Localized surface topology anomaly on {color} brick ({defect_label}, score {score:.2f}) "
            f"exceeded NPU PatchCore reference distribution; executed {action} containment policy."
        )

    return {
        "root_cause": root_cause,
        "suggested_threshold": suggested_threshold,
        "provider": "fallback",
    }


def _build_payloads(
    cycle: dict[str, Any],
    model: str,
    img_url: Optional[str],
) -> tuple[dict[str, Any], Optional[dict[str, Any]]]:
    """Construct primary (multimodal if image available) and compact text-only retry payloads."""
    cycle_id = str(cycle.get("cycle_id") or "CYC-unknown")
    color = str(cycle.get("color") or "unknown")
    defect_label = str(cycle.get("defect_label") or "Unspecified")
    action = str(cycle.get("action") or "UNKNOWN")
    try:
        score = float(cycle.get("anomaly_score", 0.0))
    except (TypeError, ValueError):
        score = 0.0

    latencies = cycle.get("latencies") if isinstance(cycle.get("latencies"), dict) else {}
    npu_ms = latencies.get("npu_ms", latencies.get("npu_anomalib_ms"))
    igpu_ms = latencies.get("igpu_ms", latencies.get("igpu_vla_ms"))
    total_ms = latencies.get("total_ms")

    system_prompt = (
        "You are NVIDIA Nemotron 3.5 Super VL on Verda B300 auditing an Intel Core Ultra X9 388H "
        "robotic Duplo brick inspection cell (Anomalib PatchCore on 50 TOPS NPU + SmolVLA on Xe3 iGPU). "
        "Do not include markdown or <think> tags. Return strict JSON matching this exact schema: "
        '{"root_cause": "<1-2 sentence physical manufacturing root-cause>", '
        '"suggested_threshold": <float between 0.40 and 0.75 or null>}'
    )
    user_text = (
        f"Cycle {cycle_id}: color={color}, defect_label={defect_label!r}, "
        f"anomaly_score={score:.3f}, action={action}, "
        f"latencies_ms={{npu:{npu_ms}, igpu:{igpu_ms}, total:{total_ms}}}. "
        "Diagnose physical root cause and return suggested_threshold (0.40-0.75 only if borderline calibration is warranted, else null)."
    )

    text_only_payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.2,
        "max_tokens": 220,
    }

    if img_url is None:
        return text_only_payload, None

    multimodal_payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": {"url": img_url}},
                ],
            },
        ],
        "temperature": 0.2,
        "max_tokens": 220,
    }
    return multimodal_payload, text_only_payload


async def _execute_chat_completion(
    endpoint: str,
    headers: dict[str, str],
    primary_payload: dict[str, Any],
    retry_payload: Optional[dict[str, Any]],
) -> tuple[int, str]:
    """
    POST chat completion via httpx.AsyncClient(timeout=8.0), retrying once with a
    compact text-only payload if a multimodal request returns HTTP 400 or 422.
    """
    client_mod = httpx
    if client_mod is None:
        try:
            import httpx as client_mod  # type: ignore[no-redef]
        except ImportError:
            client_mod = None

    if client_mod is not None:
        async with client_mod.AsyncClient(timeout=8.0) as client:
            resp = await client.post(endpoint, headers=headers, json=primary_payload)
            if resp.status_code in (400, 422) and retry_payload is not None:
                logger.info(
                    "Nemotron multimodal call returned HTTP %d; retrying compact text-only payload.",
                    int(resp.status_code),
                )
                resp = await client.post(endpoint, headers=headers, json=retry_payload)
            return int(resp.status_code), resp.text

    # Fallback transport only when httpx has not yet been installed in the environment.
    import requests

    def _sync_request() -> tuple[int, str]:
        resp = requests.post(endpoint, headers=headers, json=primary_payload, timeout=8.0)
        if resp.status_code in (400, 422) and retry_payload is not None:
            logger.info(
                "Nemotron multimodal call returned HTTP %d; retrying compact text-only payload.",
                int(resp.status_code),
            )
            resp = requests.post(endpoint, headers=headers, json=retry_payload, timeout=8.0)
        return int(resp.status_code), resp.text

    return await asyncio.to_thread(_sync_request)


async def analyze_cycle_with_nemotron(cycle: dict) -> dict:
    """
    Analyze an inspection cycle with Nemotron 3.5 Super VL on Verda B300.

    Returns:
        {
            "root_cause": str,
            "suggested_threshold": float | None,
            "provider": "verda_b300" | "fallback",
        }
    """
    global _last_call_live

    cycle_data = cycle if isinstance(cycle, dict) else {}
    base_url, model, api_key = _get_config()

    try:
        if not base_url:
            raise ValueError("NEMOTRON_BASE_URL is empty")

        endpoint = f"{base_url.rstrip('/')}/chat/completions"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        img_url = _extract_image_url(cycle_data)
        primary_payload, retry_payload = _build_payloads(cycle_data, model, img_url)

        status_code, response_text = await _execute_chat_completion(
            endpoint=endpoint,
            headers=headers,
            primary_payload=primary_payload,
            retry_payload=retry_payload,
        )

        if status_code != 200:
            logger.warning(
                "Nemotron B300 request returned HTTP %d. Falling back to deterministic analysis.",
                status_code,
            )
            _last_call_live = False
            return _heuristic_fallback_analysis(cycle_data)

        root_cause, suggested_threshold = _parse_completion_json(response_text)
        _last_call_live = True
        return {
            "root_cause": root_cause,
            "suggested_threshold": suggested_threshold,
            "provider": "verda_b300",
        }

    except Exception as exc:
        # Log ONLY exception class name — never raw exception strings, URLs, or headers.
        logger.warning(
            "Nemotron B300 analysis failed (%s). Falling back to deterministic analysis.",
            type(exc).__name__,
        )
        _last_call_live = False
        return _heuristic_fallback_analysis(cycle_data)


def get_nemotron_status() -> dict:
    """
    Return honest connectivity and configuration status for GET /api/health.
    """
    base_url, model, api_key = _get_config()

    if _last_call_live is True:
        return {
            "configured": True,
            "live": True,
            "mode": "LIVE",
            "detail": f"{model} (Verda B300)",
        }

    if _last_call_live is False:
        return {
            "configured": bool(api_key or base_url),
            "live": False,
            "mode": "FALLBACK",
            "detail": "Verda B300 unreachable · heuristic fallback",
        }

    if api_key:
        return {
            "configured": True,
            "live": True,
            "mode": "LIVE",
            "detail": f"{model} configured",
        }

    return {
        "configured": bool(base_url),
        "live": False,
        "mode": "FALLBACK",
        "detail": "Verda B300 standby (unverified / no key)",
    }
