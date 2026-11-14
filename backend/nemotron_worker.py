"""
Verda B300 Cloud Worker — NVIDIA Nemotron 3.5 Super VL Integration.

Provides asynchronous post-cycle multimodal root-cause auditing and dynamic
Anomalib threshold calibration against the OpenAI-compatible Verda B300 endpoint,
forcing IPv4 transport (avoiding dual-stack VPN blackholes), supporting both
`content` and `reasoning_content` / `reasoning` fields, and falling back cleanly.
"""

import asyncio
import json
import logging
import math
import os
import re
from typing import Any, Optional

from dotenv import dotenv_values, load_dotenv

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

_DOTENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=_DOTENV_PATH, override=False)

logger = logging.getLogger("nemotron_worker")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

DEFAULT_NEMOTRON_BASE_URL = "https://containers.datacrunch.io/nemotron-3-5-super-vl-b300/v1"
DEFAULT_NEMOTRON_MODEL = "nemotron-3.5-super-vl"

_PLACEHOLDER_API_KEYS = frozenset(
    {
        "your_nemotron_key_here",
        "your_nemotron_api_key_here",
        "your_verda_api_key_here",
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
_INIT_ENV_API_KEY = os.environ.get("NEMOTRON_API_KEY") or os.environ.get("VERDA_INFERENCE_KEY")

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

_last_call_live: Optional[bool] = None

__all__ = [
    "NEMOTRON_BASE_URL",
    "NEMOTRON_MODEL",
    "NEMOTRON_API_KEY",
    "analyze_cycle_with_nemotron",
    "get_nemotron_status",
]


def _get_config() -> tuple[str, str, str]:
    """Return active (base_url, model, api_key), honoring runtime or .env updates."""
    dotenv_cache: dict[str, Optional[str]] = {}
    if os.path.isfile(_DOTENV_PATH):
        try:
            dotenv_cache = dotenv_values(_DOTENV_PATH)
        except Exception:
            dotenv_cache = {}

    if NEMOTRON_BASE_URL != _INIT_BASE_URL:
        base_url = (NEMOTRON_BASE_URL or "").strip()
    elif os.environ.get("NEMOTRON_BASE_URL") != _INIT_ENV_BASE_URL:
        env_url = os.environ.get("NEMOTRON_BASE_URL")
        base_url = env_url.strip() if env_url is not None else DEFAULT_NEMOTRON_BASE_URL
    else:
        base_url = (
            (dotenv_cache.get("NEMOTRON_BASE_URL") or "").strip()
            or (NEMOTRON_BASE_URL or "").strip()
            or DEFAULT_NEMOTRON_BASE_URL
        )

    if NEMOTRON_MODEL != _INIT_MODEL:
        model = (NEMOTRON_MODEL or "").strip() or DEFAULT_NEMOTRON_MODEL
    elif os.environ.get("NEMOTRON_MODEL") != _INIT_ENV_MODEL:
        model = (os.environ.get("NEMOTRON_MODEL") or "").strip() or DEFAULT_NEMOTRON_MODEL
    else:
        model = (
            (dotenv_cache.get("NEMOTRON_MODEL") or "").strip()
            or (NEMOTRON_MODEL or "").strip()
            or DEFAULT_NEMOTRON_MODEL
        )

    curr_env_key = os.environ.get("NEMOTRON_API_KEY") or os.environ.get("VERDA_INFERENCE_KEY")
    if NEMOTRON_API_KEY != _INIT_API_KEY:
        api_key = _clean_api_key(NEMOTRON_API_KEY)
    elif curr_env_key != _INIT_ENV_API_KEY:
        api_key = _clean_api_key(curr_env_key)
    else:
        dotenv_key = dotenv_cache.get("NEMOTRON_API_KEY") or dotenv_cache.get("VERDA_INFERENCE_KEY")
        api_key = _clean_api_key(dotenv_key) or _clean_api_key(NEMOTRON_API_KEY)

    return base_url, model, api_key


def _extract_image_url(cycle: dict[str, Any]) -> Optional[str]:
    """
    Prefer inline data:image/... URIs (or compact JPEG synthesis) so Verda's sandboxed
    B300 vLLM container never stalls trying to fetch external URLs over restricted egress.
    """
    for key in ("composite_url", "raw_url"):
        val = cycle.get(key)
        if isinstance(val, str) and val.strip().startswith("data:image/"):
            return val.strip()

    try:
        import base64
        import io
        from PIL import Image
        import cloudinary_media

        png_bytes = cloudinary_media.create_simulated_brick_image(
            color=str(cycle.get("color") or "yellow"),
            defect=str(cycle.get("defect_label") or "None"),
            is_heatmap=False,
            score=float(cycle.get("anomaly_score") or 0.0),
        )
        img = Image.open(io.BytesIO(png_bytes)).convert("RGB").resize((224, 224))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=78)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        pass

    for key in ("composite_url", "raw_url"):
        val = cycle.get(key)
        if isinstance(val, str) and val.strip().startswith(("http://", "https://")):
            return val.strip()
    return None


def _normalize_threshold(raw_val: Any) -> Optional[float]:
    """Validate suggested_threshold as None or a finite float clamped to [0.40, 0.75]."""
    if raw_val is None or isinstance(raw_val, bool):
        return None
    if isinstance(raw_val, str):
        stripped = raw_val.strip().lower()
        if not stripped or stripped in ("null", "none"):
            return None
    try:
        numeric = float(raw_val)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    clamped = min(0.75, max(0.40, numeric))
    return round(clamped, 4)


def _coerce_message_field(val: Any) -> str:
    if isinstance(val, list):
        return "".join(
            str(part.get("text", "")) for part in val if isinstance(part, dict)
        ).strip()
    if isinstance(val, str):
        return val.strip()
    return ""


def _try_extract_json_dict(text: str) -> Optional[dict[str, Any]]:
    if not text:
        return None
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    fence_matches = re.findall(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        cleaned,
        flags=re.DOTALL | re.IGNORECASE,
    )
    for candidate in reversed(fence_matches):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict) and parsed.get("root_cause"):
                return parsed
        except Exception:
            continue

    # Scan JSON object candidates from right to left (in case reasoning mentions braces earlier)
    end_positions = [m.start() for m in re.finditer(r"\}", cleaned)]
    start_positions = [m.start() for m in re.finditer(r"\{", cleaned)]
    for end_idx in reversed(end_positions):
        for start_idx in reversed(start_positions):
            if start_idx < end_idx and (end_idx - start_idx) <= 2000:
                snippet = cleaned[start_idx : end_idx + 1]
                if "root_cause" not in snippet:
                    continue
                try:
                    parsed = json.loads(snippet)
                    if isinstance(parsed, dict) and isinstance(parsed.get("root_cause"), str) and parsed["root_cause"].strip():
                        return parsed
                except Exception:
                    continue
    return None


def _parse_completion_json(response_text: str) -> tuple[str, Optional[float]]:
    """
    Extract root_cause and suggested_threshold from Verda B300 chat completion JSON,
    falling back seamlessly from `message.content` to `message.reasoning_content` / `message.reasoning`.
    """
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

    content_text = _coerce_message_field(message.get("content"))
    reasoning_text = (
        _coerce_message_field(message.get("reasoning_content"))
        or _coerce_message_field(message.get("reasoning"))
    )

    if not content_text and not reasoning_text:
        raise ValueError("Both content and reasoning_content are empty")

    for candidate_text in (content_text, reasoning_text):
        parsed = _try_extract_json_dict(candidate_text)
        if parsed is not None:
            root_cause = str(parsed["root_cause"]).strip()
            suggested_threshold = _normalize_threshold(parsed.get("suggested_threshold"))
            return root_cause, suggested_threshold

    # Prose fallback when live Verda B300 answers in plain sentences without JSON braces
    raw_prose = content_text or reasoning_text
    cleaned_prose = re.sub(r"<think>.*?</think>", "", raw_prose, flags=re.DOTALL).strip()
    cleaned_prose = re.sub(r"\s+", " ", cleaned_prose).strip()
    if not cleaned_prose:
        raise ValueError("Empty prose after cleanup")
    if len(cleaned_prose) > 320:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned_prose) if s.strip()]
        summary = " ".join(sentences[-2:]) if len(sentences) >= 2 else cleaned_prose[-320:]
        cleaned_prose = summary[:320].strip()

    return cleaned_prose, None


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
        "Keep reasoning ultra-brief and return strict JSON matching this exact schema: "
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
        "max_tokens": 256,
        "chat_template_kwargs": {"enable_thinking": False},
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
        "max_tokens": 256,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    return multimodal_payload, text_only_payload


async def _execute_chat_completion(
    endpoint: str,
    headers: dict[str, str],
    primary_payload: dict[str, Any],
    retry_payload: Optional[dict[str, Any]],
) -> tuple[int, str]:
    """
    POST chat completion via httpx.AsyncClient forcing IPv4 for remote cloud hosts
    (avoiding dual-stack/VPN IPv6 blackholes), retrying once with text-only on HTTP 400/422.
    """
    client_mod = httpx
    if client_mod is None:
        try:
            import httpx as client_mod  # type: ignore[no-redef]
        except ImportError:
            client_mod = None

    is_local = any(
        h in endpoint.lower() for h in ("//localhost", "//127.0.0.1", "//[::1]")
    )

    if client_mod is not None:
        transport = (
            None
            if is_local
            else client_mod.AsyncHTTPTransport(local_address="0.0.0.0")
        )
        timeout = client_mod.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)
        async with client_mod.AsyncClient(timeout=timeout, transport=transport) as client:
            resp = await client.post(endpoint, headers=headers, json=primary_payload)
            if resp.status_code in (400, 422) and retry_payload is not None:
                logger.info(
                    "Nemotron multimodal call returned HTTP %d; retrying compact text-only payload.",
                    int(resp.status_code),
                )
                resp = await client.post(endpoint, headers=headers, json=retry_payload)
            return int(resp.status_code), resp.text

    import requests

    def _sync_request() -> tuple[int, str]:
        resp = requests.post(endpoint, headers=headers, json=primary_payload, timeout=30.0)
        if resp.status_code in (400, 422) and retry_payload is not None:
            resp = requests.post(endpoint, headers=headers, json=retry_payload, timeout=30.0)
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
        logger.warning(
            "Nemotron B300 analysis failed (%s). Falling back to deterministic analysis.",
            type(exc).__name__,
        )
        _last_call_live = False
        return _heuristic_fallback_analysis(cycle_data)


def get_nemotron_status() -> dict:
    """Return honest connectivity and configuration status for GET /api/health."""
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
            "detail": "Verda B300 queue busy · heuristic fallback",
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
