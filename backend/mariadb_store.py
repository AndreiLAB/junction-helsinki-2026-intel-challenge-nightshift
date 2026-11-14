"""
MariaDB 11.7+ Vector Telemetry Store (`VECTOR(512)` + `VEC_DISTANCE_COSINE`)
with deterministic pure-Python/Pillow 512-dim brick embeddings and seamless
in-memory cosine similarity fallback.

Designed for Windows Python 3.14+ compatibility using pure-Python `pymysql`
(guarded with `try/except ImportError`) and `asyncio.to_thread`.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import logging
import math
import os
import re
import ssl
import threading
import urllib.parse
import uuid
from typing import Any, Optional

from dotenv import dotenv_values, load_dotenv
from PIL import Image

_DOTENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
# Load backend/.env without overriding already-exported environment variables.
load_dotenv(dotenv_path=_DOTENV_PATH, override=False)

for _scheme in ("mariadb", "mysql", "mariadb+pymysql", "mysql+pymysql"):
    if _scheme not in urllib.parse.uses_netloc:
        urllib.parse.uses_netloc.append(_scheme)
    if _scheme not in urllib.parse.uses_query:
        urllib.parse.uses_query.append(_scheme)

logger = logging.getLogger("mariadb_store")

try:
    import pymysql
    import pymysql.cursors

    _PYMYSQL_AVAILABLE = True
except ImportError:
    pymysql = None  # type: ignore[assignment]
    _PYMYSQL_AVAILABLE = False

EMBEDDING_DIM = 512
MEMORY_CAP = 200
DEFAULT_PORT = 3306
DEFAULT_DATABASE = "junction_physical_ai"

# Module-level state for MariaDB health and 200-entry in-memory vector store
_memory_records: list[dict[str, Any]] = []
_memory_policy_history: list[dict[str, Any]] = []
_memory_lock = threading.Lock()
_db_lock = threading.Lock()
_db_live: bool = False
_schema_initialized_key: Optional[tuple[str, int, str]] = None

_PLACEHOLDER_MARKERS = (
    "your_mariadb_uri_here",
    "localhost_placeholder",
    "your_host_here",
    "your_mariadb_host",
    "your_user_here",
    "your_password_here",
    "placeholder",
    "changeme",
    "example.com",
    "<host>",
    "<user>",
)

_COLOR_PALETTE_NORM: dict[str, tuple[float, float, float]] = {
    "blue": (30.0 / 255.0, 115.0 / 255.0, 230.0 / 255.0),
    "yellow": (245.0 / 255.0, 195.0 / 255.0, 30.0 / 255.0),
    "red": (225.0 / 255.0, 45.0 / 255.0, 45.0 / 255.0),
    "green": (35.0 / 255.0, 180.0 / 255.0, 85.0 / 255.0),
    "orange": (245.0 / 255.0, 120.0 / 255.0, 25.0 / 255.0),
    "cyan": (30.0 / 255.0, 200.0 / 255.0, 235.0 / 255.0),
    "purple": (150.0 / 255.0, 60.0 / 255.0, 220.0 / 255.0),
    "white": (235.0 / 255.0, 238.0 / 255.0, 242.0 / 255.0),
    "gray": (90.0 / 255.0, 98.0 / 255.0, 112.0 / 255.0),
    "grey": (90.0 / 255.0, 98.0 / 255.0, 112.0 / 255.0),
    "black": (42.0 / 255.0, 46.0 / 255.0, 54.0 / 255.0),
}

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS inspection_cycles (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    cycle_id VARCHAR(64) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    color VARCHAR(32),
    defect_label VARCHAR(128),
    anomaly_score FLOAT,
    action VARCHAR(32),
    npu_ms FLOAT,
    igpu_ms FLOAT,
    cpu_ms FLOAT,
    total_ms FLOAT,
    raw_url MEDIUMTEXT,
    composite_url MEDIUMTEXT,
    nemotron_reasoning TEXT,
    embedding VECTOR(512) NOT NULL,
    UNIQUE KEY uq_cycle_id (cycle_id),
    VECTOR INDEX idx_cycle_embedding (embedding) M=8 DISTANCE=cosine
) ENGINE=InnoDB
"""

_CREATE_TABLE_FALLBACK_SQL = """
CREATE TABLE IF NOT EXISTS inspection_cycles (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    cycle_id VARCHAR(64) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    color VARCHAR(32),
    defect_label VARCHAR(128),
    anomaly_score FLOAT,
    action VARCHAR(32),
    npu_ms FLOAT,
    igpu_ms FLOAT,
    cpu_ms FLOAT,
    total_ms FLOAT,
    raw_url MEDIUMTEXT,
    composite_url MEDIUMTEXT,
    nemotron_reasoning TEXT,
    embedding VECTOR(512) NOT NULL,
    UNIQUE KEY uq_cycle_id (cycle_id),
    VECTOR INDEX idx_cycle_embedding (embedding)
) ENGINE=InnoDB
"""

_FIND_SIMILAR_SQL = (
    "SELECT cycle_id, color, defect_label, action, anomaly_score, "
    "VEC_DISTANCE_COSINE(embedding, VEC_FromText(%s)) AS dist "
    "FROM inspection_cycles "
    "WHERE cycle_id != %s "
    "ORDER BY dist ASC "
    "LIMIT %s"
)

_FETCH_CYCLE_EMBEDDING_SQL = (
    "SELECT VEC_ToText(embedding) AS vec_text "
    "FROM inspection_cycles "
    "WHERE cycle_id = %s "
    "LIMIT 1"
)

_UPSERT_CYCLE_SQL = """
INSERT INTO inspection_cycles (
    cycle_id, color, defect_label, anomaly_score, action,
    npu_ms, igpu_ms, cpu_ms, total_ms,
    raw_url, composite_url, nemotron_reasoning, embedding
) VALUES (
    %s, %s, %s, %s, %s,
    %s, %s, %s, %s,
    %s, %s, %s, VEC_FromText(%s)
)
ON DUPLICATE KEY UPDATE
    color = VALUES(color),
    defect_label = VALUES(defect_label),
    anomaly_score = VALUES(anomaly_score),
    action = VALUES(action),
    npu_ms = VALUES(npu_ms),
    igpu_ms = VALUES(igpu_ms),
    cpu_ms = VALUES(cpu_ms),
    total_ms = VALUES(total_ms),
    raw_url = VALUES(raw_url),
    composite_url = VALUES(composite_url),
    nemotron_reasoning = VALUES(nemotron_reasoning),
    embedding = VALUES(embedding)
"""

_CREATE_POLICIES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS sorting_policies (
    policy_id VARCHAR(64) PRIMARY KEY,
    source VARCHAR(32) NOT NULL,
    event_type VARCHAR(32) NOT NULL,
    target_brick_color VARCHAR(32),
    defect_description VARCHAR(255),
    action_on_match VARCHAR(32),
    anomaly_threshold FLOAT NOT NULL,
    active_global_threshold FLOAT NOT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    reasoning TEXT
) WITH SYSTEM VERSIONING ENGINE=InnoDB
"""

_UPSERT_POLICY_SQL = """
INSERT INTO sorting_policies (
    policy_id, source, event_type, target_brick_color, defect_description,
    action_on_match, anomaly_threshold, active_global_threshold, is_active, reasoning
) VALUES (
    %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s
)
ON DUPLICATE KEY UPDATE
    source = VALUES(source),
    event_type = VALUES(event_type),
    target_brick_color = VALUES(target_brick_color),
    defect_description = VALUES(defect_description),
    action_on_match = VALUES(action_on_match),
    anomaly_threshold = VALUES(anomaly_threshold),
    active_global_threshold = VALUES(active_global_threshold),
    is_active = VALUES(is_active),
    reasoning = VALUES(reasoning)
"""

_QUERY_POLICY_HISTORY_SQL = (
    "SELECT policy_id, source, event_type, target_brick_color, defect_description, "
    "action_on_match, anomaly_threshold, active_global_threshold, is_active, reasoning, "
    "DATE_FORMAT(row_start, '%%Y-%%m-%%d %%H:%%i:%%s.%%f') AS valid_from, "
    "IF(YEAR(row_end) >= 2038, NULL, DATE_FORMAT(row_end, '%%Y-%%m-%%d %%H:%%i:%%s.%%f')) AS valid_to, "
    "IF(YEAR(row_end) >= 2038, 1, 0) AS is_current "
    "FROM sorting_policies "
    "FOR SYSTEM_TIME ALL "
    "ORDER BY row_start DESC "
    "LIMIT %s"
)


def _is_placeholder(value: Optional[str]) -> bool:
    if value is None:
        return True
    cleaned = value.strip().lower()
    if not cleaned or cleaned in ("none", "null", "false"):
        return True
    return any(marker in cleaned for marker in _PLACEHOLDER_MARKERS)


_LOCAL_DB_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0"})


def _is_local_host(host: Optional[str]) -> bool:
    if not host:
        return True
    cleaned = host.strip().lower()
    return cleaned in _LOCAL_DB_HOSTS or cleaned.endswith(".localhost")


def _read_env_setting(key: str, dotenv_cache: Optional[dict[str, Optional[str]]] = None) -> str:
    val = os.environ.get(key)
    if val is not None and val.strip():
        return val.strip()
    if dotenv_cache is not None:
        raw = dotenv_cache.get(key)
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    return ""


def _create_encrypted_tls_context() -> ssl.SSLContext:
    """
    Creates a TLS 1.2+ client context matching MySQL/MariaDB `ssl_mode=REQUIRED`
    (encrypted transport without failing when hosted DBs use provider-private CAs).
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _build_ssl_param(
    ssl_setting: Optional[str],
    host: Optional[str] = None,
    ssl_ca: Optional[str] = None,
) -> Any:
    val = (ssl_setting or "").strip()
    val_lower = val.lower()

    # Explicit disable via MARIADB_SSL=false / ?ssl=false / ?ssl_mode=DISABLED
    if val_lower in ("0", "false", "no", "off", "disable", "disabled"):
        return None

    if ssl_ca and os.path.isfile(ssl_ca):
        return ssl.create_default_context(cafile=ssl_ca)

    if val and os.path.isfile(val):
        return ssl.create_default_context(cafile=val)

    if val_lower == "verify_identity":
        return ssl.create_default_context()

    if val_lower == "verify_ca":
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        return ctx

    if val_lower in (
        "1",
        "true",
        "yes",
        "on",
        "required",
        "preferred",
        "skip-verify",
        "insecure",
        "allow",
    ):
        return _create_encrypted_tls_context()

    # Automatically enable TLS when connecting to any non-localhost (cloud/hosted) MariaDB
    if host and not _is_local_host(host):
        return _create_encrypted_tls_context()

    return None


def _parse_db_config() -> Optional[dict[str, Any]]:
    """
    Resolves MariaDB connection parameters from MARIADB_URI (`mysql://` or `mariadb://`)
    or discrete MARIADB_* env vars (including live reloads from `backend/.env`).
    Returns None when unconfigured or set to placeholder values.
    """
    dotenv_cache: dict[str, Optional[str]] = {}
    if os.path.isfile(_DOTENV_PATH):
        try:
            dotenv_cache = dotenv_values(_DOTENV_PATH)
        except Exception:
            dotenv_cache = {}

    uri = _read_env_setting("MARIADB_URI", dotenv_cache)
    env_ssl = _read_env_setting("MARIADB_SSL", dotenv_cache)
    env_ssl_ca = _read_env_setting("MARIADB_SSL_CA", dotenv_cache) or None
    default_db = _read_env_setting("MARIADB_DATABASE", dotenv_cache) or DEFAULT_DATABASE

    if uri and not _is_placeholder(uri):
        parsed = urllib.parse.urlparse(uri)
        base_scheme = (parsed.scheme or "").lower().split("+", 1)[0]
        if base_scheme in ("mysql", "mariadb") and parsed.hostname and not _is_placeholder(parsed.hostname):
            try:
                port = int(parsed.port or DEFAULT_PORT)
            except ValueError:
                port = DEFAULT_PORT
            user = urllib.parse.unquote(parsed.username) if parsed.username else "root"
            if _is_placeholder(user):
                return None
            password = urllib.parse.unquote(parsed.password) if parsed.password else ""
            db_path = (parsed.path or "").lstrip("/")
            database = urllib.parse.unquote(db_path) if db_path else default_db
            if _is_placeholder(database):
                database = DEFAULT_DATABASE

            query_params = {
                k.lower().replace("-", "_"): v
                for k, v in urllib.parse.parse_qs(parsed.query).items()
            }
            uri_ssl = (
                query_params.get("ssl", [""])[0]
                or query_params.get("tls", [""])[0]
                or query_params.get("ssl_mode", [""])[0]
                or env_ssl
            )
            uri_ssl_ca = query_params.get("ssl_ca", [""])[0] or env_ssl_ca

            return {
                "host": parsed.hostname,
                "port": port,
                "user": user,
                "password": password,
                "database": database,
                "ssl": _build_ssl_param(uri_ssl, host=parsed.hostname, ssl_ca=uri_ssl_ca),
            }

    host = _read_env_setting("MARIADB_HOST", dotenv_cache)
    if not host or _is_placeholder(host):
        return None

    user = _read_env_setting("MARIADB_USER", dotenv_cache) or "root"
    if _is_placeholder(user):
        return None

    password = os.environ.get("MARIADB_PASSWORD")
    if password is None and dotenv_cache:
        password = dotenv_cache.get("MARIADB_PASSWORD") or ""
    password = password or ""
    if password and _is_placeholder(password):
        return None

    port_raw = _read_env_setting("MARIADB_PORT", dotenv_cache) or str(DEFAULT_PORT)
    try:
        port = int(port_raw) if port_raw else DEFAULT_PORT
    except ValueError:
        port = DEFAULT_PORT

    database = default_db if not _is_placeholder(default_db) else DEFAULT_DATABASE

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database,
        "ssl": _build_ssl_param(env_ssl, host=host, ssl_ca=env_ssl_ca),
    }


def _decode_pil_image(raw_image_data: bytes | str | None) -> Optional[Image.Image]:
    """
    Decodes bytes or a base64 Data URI into a PIL Image without performing network I/O.
    Returns None for HTTP(S) URLs, None, or non-image strings.
    """
    if raw_image_data is None:
        return None

    if isinstance(raw_image_data, (bytes, bytearray, memoryview)):
        raw_bytes = bytes(raw_image_data)
        if not raw_bytes:
            return None
        try:
            img = Image.open(io.BytesIO(raw_bytes))
            img.load()
            return img
        except Exception:
            return None

    if isinstance(raw_image_data, str):
        s = raw_image_data.strip()
        if not s or s.startswith(("http://", "https://")):
            return None

        if s.startswith("data:image/") and "," in s:
            _, b64_payload = s.split(",", 1)
            try:
                raw_bytes = base64.b64decode(b64_payload, validate=False)
                img = Image.open(io.BytesIO(raw_bytes))
                img.load()
                return img
            except Exception:
                return None

        # Support raw base64-encoded image payloads (e.g. CycleIngestRequest.raw_image_b64)
        if len(s) >= 64 and " " not in s and not s.startswith(("sim_", "raw_", "init_", "heat_")):
            try:
                raw_bytes = base64.b64decode(s, validate=False)
                img = Image.open(io.BytesIO(raw_bytes))
                img.load()
                return img
            except Exception:
                return None

    return None


def _compute_rgb_luma_histogram_32(rgb_floats: list[float]) -> list[float]:
    """
    Computes a 32-bin normalized color/luminance histogram (8 R + 8 G + 8 B + 8 Y)
    from flattened [r, g, b, ...] floats in [0.0, 1.0].
    """
    hist = [0.0] * 32
    num_pixels = max(1, len(rgb_floats) // 3)
    for idx in range(0, len(rgb_floats) - 2, 3):
        r = max(0.0, min(1.0, rgb_floats[idx]))
        g = max(0.0, min(1.0, rgb_floats[idx + 1]))
        b = max(0.0, min(1.0, rgb_floats[idx + 2]))
        luma = max(0.0, min(1.0, 0.299 * r + 0.587 * g + 0.114 * b))

        r_bin = min(7, int(r * 8.0))
        g_bin = min(7, int(g * 8.0))
        b_bin = min(7, int(b * 8.0))
        y_bin = min(7, int(luma * 8.0))

        hist[r_bin] += 1.0
        hist[8 + g_bin] += 1.0
        hist[16 + b_bin] += 1.0
        hist[24 + y_bin] += 1.0

    inv_n = 1.0 / float(num_pixels)
    return [v * inv_n for v in hist]


def _visual_features_from_image(img: Image.Image) -> list[float]:
    """
    Extracts 480 deterministic visual features from a PIL Image:
      - 384 normalized RGB spatial features (16x8x3)
      - 64 grayscale horizontal/vertical gradient magnitudes (8x8)
      - 32-bin RGB + luminance histogram
    """
    resample = getattr(Image, "Resampling", Image).BILINEAR
    rgb_img = img.convert("RGB")

    # 1. 16x8 spatial RGB -> 384 floats in [0, 1]
    spatial_rgb = rgb_img.resize((16, 8), resample)
    spatial_vec = [b / 255.0 for b in spatial_rgb.tobytes()]

    # 2. 8x8 grayscale horizontal/vertical gradient magnitudes -> 64 floats in [0, 1]
    gray_9x9 = rgb_img.convert("L").resize((9, 9), resample)
    g_bytes = gray_9x9.tobytes()
    inv_sqrt2 = 1.0 / math.sqrt(2.0)
    edge_vec: list[float] = []
    for y in range(8):
        row_off = y * 9
        next_row_off = (y + 1) * 9
        for x in range(8):
            p00 = g_bytes[row_off + x] / 255.0
            p10 = g_bytes[row_off + x + 1] / 255.0
            p01 = g_bytes[next_row_off + x] / 255.0
            gx = p10 - p00
            gy = p01 - p00
            edge_vec.append(min(1.0, math.sqrt(gx * gx + gy * gy) * inv_sqrt2))

    # 3. 32-bin RGB + luminance histogram -> 32 floats in [0, 1]
    hist_32x32 = rgb_img.resize((32, 32), resample)
    hist_floats = [b / 255.0 for b in hist_32x32.tobytes()]
    hist_vec = _compute_rgb_luma_histogram_32(hist_floats)

    return spatial_vec + edge_vec + hist_vec


def _classify_defect_category(defect_norm: str) -> str:
    if not defect_norm or any(k in defect_norm for k in ("pristine", "none", "perfect", "good", "clean", "normal")):
        return "pristine"
    if any(k in defect_norm for k in ("scratch", "groove", "scuff", "abrasion", "gouge")):
        return "scratch"
    if any(k in defect_norm for k in ("crack", "stud", "split", "fracture", "deform")):
        return "crack"
    if any(k in defect_norm for k in ("stripe", "marker", "line", "ink", "stain", "contaminat", "discolor")):
        return "stripe"
    if any(k in defect_norm for k in ("chip", "corner", "dent", "missing", "nick")):
        return "chip"
    if any(k in defect_norm for k in ("glare", "reflect", "specular", "ambiguous", "flare", "shadow")):
        return "glare"
    return "other"


def _resolve_color_rgb(color_norm: str) -> tuple[float, float, float]:
    for key, rgb in _COLOR_PALETTE_NORM.items():
        if key in color_norm:
            return rgb
    digest = hashlib.sha256(f"brick_color:{color_norm}".encode("utf-8")).digest()
    return (
        0.15 + 0.75 * (digest[0] / 255.0),
        0.15 + 0.75 * (digest[1] / 255.0),
        0.15 + 0.75 * (digest[2] / 255.0),
    )


def _synthetic_visual_features(color_norm: str, defect_norm: str, score_clamped: float) -> list[float]:
    """
    Deterministically synthesizes the 480 visual feature slots (384 spatial RGB +
    64 edge gradients + 32 color/luma histogram) from `(color, defect_label, anomaly_score)`
    using smooth spatial/color templates + `hashlib.sha256` sub-band features.
    """
    cr, cg, cb = _resolve_color_rgb(color_norm)
    bg_r, bg_g, bg_b = (15.0 / 255.0, 23.0 / 255.0, 42.0 / 255.0)
    category = _classify_defect_category(defect_norm)

    cat_digest = hashlib.sha256(f"cat:{color_norm}:{category}".encode("utf-8")).digest()
    lbl_digest = hashlib.sha256(f"lbl:{defect_norm}".encode("utf-8")).digest()

    defect_centers = {
        "pristine": (0.50, 0.50),
        "scratch": (0.64, 0.36),
        "crack": (0.50, 0.52),
        "stripe": (0.65, 0.45),
        "chip": (0.75, 0.25),
        "glare": (0.62, 0.36),
        "other": (0.60, 0.40),
    }
    dx_c, dy_c = defect_centers.get(category, (0.60, 0.40))
    defect_strength = 0.0 if category == "pristine" else max(0.15, score_clamped)

    stud_coords = ((0.36, 0.36), (0.64, 0.36), (0.36, 0.64), (0.64, 0.64))

    # 1. 16x8 spatial RGB template -> 384 floats
    spatial_vec: list[float] = []
    luma_grid_8x16: list[list[float]] = []

    for y in range(8):
        ny = (y + 0.5) / 8.0
        row_luma: list[float] = []
        for x in range(16):
            nx = (x + 0.5) / 16.0

            # Smooth Duplo brick body window in center of studio frame
            ox = max(0.0, abs(nx - 0.5) - 0.24) / 0.08
            oy = max(0.0, abs(ny - 0.5) - 0.24) / 0.08
            brick_mask = max(0.0, min(1.0, 1.0 - max(ox, oy)))

            # Subtle 2x2 top-stud bevel shading
            stud_boost = 0.0
            for sx, sy in stud_coords:
                d2 = (nx - sx) ** 2 + (ny - sy) ** 2
                if d2 < 0.012:
                    stud_boost += 0.06 * (1.0 - d2 / 0.012)

            r = bg_r * (1.0 - brick_mask) + min(1.0, cr + stud_boost) * brick_mask
            g = bg_g * (1.0 - brick_mask) + min(1.0, cg + stud_boost) * brick_mask
            b = bg_b * (1.0 - brick_mask) + min(1.0, cb + stud_boost) * brick_mask

            # Localized defect perturbation
            dist2 = (nx - dx_c) ** 2 + (ny - dy_c) ** 2
            defect_spot = math.exp(-dist2 / 0.025) * defect_strength
            if category == "glare":
                r = r + (1.0 - r) * (0.55 * defect_spot)
                g = g + (1.0 - g) * (0.55 * defect_spot)
                b = b + (1.0 - b) * (0.60 * defect_spot)
            elif category in ("scratch", "crack", "stripe", "chip", "other"):
                darken = 0.55 * defect_spot
                r = r * (1.0 - darken)
                g = g * (1.0 - darken)
                b = b * (1.0 - darken)

            # Fine deterministic sha256 sub-band texture
            idx = y * 16 + x
            sub_band = (
                0.025 * ((cat_digest[idx % 32] / 255.0) - 0.5)
                + 0.012 * ((lbl_digest[(idx * 7) % 32] / 255.0) - 0.5)
            )
            r = max(0.0, min(1.0, r + sub_band))
            g = max(0.0, min(1.0, g + sub_band))
            b = max(0.0, min(1.0, b + sub_band))

            spatial_vec.extend((r, g, b))
            row_luma.append(0.299 * r + 0.587 * g + 0.114 * b)
        luma_grid_8x16.append(row_luma)

    # Downsample 16x8 luma to 9x9 luma grid for 8x8 gradient magnitudes -> 64 floats
    luma_9x9: list[list[float]] = []
    for y in range(9):
        sy = min(7, y)
        row9: list[float] = []
        for x in range(9):
            sx = min(15, int(round(x * 15.0 / 8.0)))
            row9.append(luma_grid_8x16[sy][sx])
        luma_9x9.append(row9)

    inv_sqrt2 = 1.0 / math.sqrt(2.0)
    edge_vec: list[float] = []
    for y in range(8):
        ny = (y + 0.5) / 8.0
        for x in range(8):
            nx = (x + 0.5) / 8.0
            gx = luma_9x9[y][x + 1] - luma_9x9[y][x]
            gy = luma_9x9[y + 1][x] - luma_9x9[y][x]
            base_mag = math.sqrt(gx * gx + gy * gy) * inv_sqrt2

            # Defect high-frequency edge energy around defect locus
            dist2 = (nx - dx_c) ** 2 + (ny - dy_c) ** 2
            defect_edge = (
                0.35 * defect_strength * math.exp(-dist2 / 0.03)
                if category != "pristine"
                else 0.0
            )
            e_idx = y * 8 + x
            edge_sub = 0.015 * (cat_digest[(e_idx + 11) % 32] / 255.0)
            edge_vec.append(max(0.0, min(1.0, base_mag + defect_edge + edge_sub)))

    # 3. 32-bin RGB + luminance histogram directly over synthetic spatial pixels -> 32 floats
    hist_vec = _compute_rgb_luma_histogram_32(spatial_vec)

    return spatial_vec + edge_vec + hist_vec


def _structured_telemetry_features(color_norm: str, defect_norm: str, score_clamped: float) -> list[float]:
    """
    Computes 32 structured telemetry features:
      - 6 brick color soft/one-hot features (blue, yellow, red, green, orange, other)
      - 6 defect category indicators (pristine/none, scratch/groove, crack/stud,
        stripe/marker, chip, glare/reflection)
      - 8 anomaly_score features (7 Gaussian radial basis bins + 1 normalized scalar)
      - 12 defect_label character trigram sha256 hash bins
    Weighted slightly so structured semantics meaningfully complement the 480 visual slots.
    """
    # 1. Color soft encoding (6 floats)
    primary_colors = ("blue", "yellow", "red", "green", "orange")
    color_feats = [1.0 if c in color_norm else 0.04 for c in primary_colors]
    if "cyan" in color_norm or "navy" in color_norm:
        color_feats[0] = max(color_feats[0], 0.65)
    if "amber" in color_norm or "gold" in color_norm:
        color_feats[1] = max(color_feats[1], 0.55)
        color_feats[4] = max(color_feats[4], 0.45)
    if "crimson" in color_norm or "pink" in color_norm:
        color_feats[2] = max(color_feats[2], 0.55)
    if "lime" in color_norm or "teal" in color_norm:
        color_feats[3] = max(color_feats[3], 0.55)
    other_color = 0.0 if any(c in color_norm for c in primary_colors) else 1.0
    color_feats.append(other_color)

    # 2. Defect category indicators (6 floats)
    is_pristine = (
        1.0
        if (not defect_norm or any(k in defect_norm for k in ("pristine", "none", "perfect", "good", "clean", "normal")))
        else max(0.0, 1.0 - score_clamped * 2.2)
    )
    is_scratch = 1.0 if any(k in defect_norm for k in ("scratch", "groove", "scuff", "abrasion", "gouge")) else 0.0
    is_crack = 1.0 if any(k in defect_norm for k in ("crack", "stud", "split", "fracture", "deform")) else 0.0
    is_stripe = 1.0 if any(k in defect_norm for k in ("stripe", "marker", "line", "ink", "stain", "contaminat", "discolor")) else 0.0
    is_chip = 1.0 if any(k in defect_norm for k in ("chip", "corner", "dent", "missing", "nick")) else 0.0
    is_glare = 1.0 if any(k in defect_norm for k in ("glare", "reflect", "specular", "ambiguous", "flare", "shadow")) else 0.0
    defect_feats = [is_pristine, is_scratch, is_crack, is_stripe, is_chip, is_glare]

    # 3. Radial basis bins over anomaly_score (8 floats)
    rbf_centers = (0.08, 0.22, 0.36, 0.50, 0.64, 0.78, 0.92)
    sigma2_2 = 2.0 * (0.14 ** 2)
    score_feats = [math.exp(-((score_clamped - c) ** 2) / sigma2_2) for c in rbf_centers]
    score_feats.append(score_clamped)

    # 4. Defect label character trigram hashes (12 floats)
    cleaned_lbl = re.sub(r"[^a-z0-9]+", " ", defect_norm).strip() or "none"
    padded = f"<{cleaned_lbl}>"
    trigram_bins = [0.0] * 12
    for i in range(max(1, len(padded) - 2)):
        tri = padded[i : i + 3]
        digest = hashlib.sha256(tri.encode("utf-8")).digest()
        trigram_bins[digest[0] % 12] += 1.0
    max_tri = max(trigram_bins) or 1.0
    trigram_feats = [v / max_tri for v in trigram_bins]

    raw_32 = color_feats + defect_feats + score_feats + trigram_feats
    # Scale structured telemetry slots by 1.35 so color/defect/score semantics balance 480 visual slots
    return [v * 1.35 for v in raw_32]


def _l2_normalize_512(vec: list[float]) -> list[float]:
    if len(vec) < EMBEDDING_DIM:
        vec = list(vec) + [0.0] * (EMBEDDING_DIM - len(vec))
    elif len(vec) > EMBEDDING_DIM:
        vec = list(vec[:EMBEDDING_DIM])

    clean = [float(v) if math.isfinite(v) else 0.0 for v in vec]
    norm = math.sqrt(sum(v * v for v in clean))
    if norm <= 0.0:
        clean[0] = 1.0
        norm = 1.0
    return [round(v / norm, 6) for v in clean]


def compute_brick_embedding(
    raw_image_data: bytes | str | None,
    color: str,
    defect_label: str,
    anomaly_score: float,
) -> list[float]:
    """
    Computes a deterministic 512-float L2-normalized embedding for a brick inspection cycle.
    Combines 480 visual features (PIL 16x8 RGB + 8x8 edge gradients + 32-bin color/luma histogram,
    or deterministic smooth template + sha256 sub-band synthesis) with 32 structured telemetry features.
    """
    color_norm = (color or "blue").strip().lower() or "blue"
    defect_norm = (defect_label or "none").strip().lower() or "none"
    try:
        score_val = float(anomaly_score) if anomaly_score is not None else 0.0
        if not math.isfinite(score_val):
            score_val = 0.0
    except (TypeError, ValueError):
        score_val = 0.0
    score_clamped = max(0.0, min(1.0, score_val))

    pil_img = _decode_pil_image(raw_image_data)
    if pil_img is not None:
        try:
            visual_480 = _visual_features_from_image(pil_img)
        except Exception:
            visual_480 = _synthetic_visual_features(color_norm, defect_norm, score_clamped)
        finally:
            try:
                pil_img.close()
            except Exception:
                pass
    else:
        visual_480 = _synthetic_visual_features(color_norm, defect_norm, score_clamped)

    structured_32 = _structured_telemetry_features(color_norm, defect_norm, score_clamped)
    return _l2_normalize_512(visual_480 + structured_32)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (norm_a * norm_b)


def _upsert_memory_record(
    cycle_id: str,
    color: str,
    defect_label: str,
    action: str,
    anomaly_score: float,
    embedding: list[float],
) -> None:
    record = {
        "cycle_id": cycle_id,
        "color": color,
        "defect_label": defect_label,
        "action": action,
        "anomaly_score": float(anomaly_score),
        "embedding": list(embedding),
    }
    with _memory_lock:
        for idx, existing in enumerate(_memory_records):
            if existing.get("cycle_id") == cycle_id:
                _memory_records.pop(idx)
                break
        _memory_records.insert(0, record)
        if len(_memory_records) > MEMORY_CAP:
            del _memory_records[MEMORY_CAP:]


def _memory_find_similar(
    embedding: list[float],
    exclude_cycle_id: str,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    limit = max(0, int(top_k))
    if limit == 0:
        return []

    with _memory_lock:
        candidates = [r for r in _memory_records if r.get("cycle_id") != exclude_cycle_id]

    scored: list[tuple[float, dict[str, Any]]] = []
    for rec in candidates:
        rec_emb = rec.get("embedding")
        if not rec_emb:
            continue
        cos_sim = _cosine_similarity(embedding, rec_emb)
        scored.append((cos_sim, rec))

    scored.sort(key=lambda item: item[0], reverse=True)

    results: list[dict[str, Any]] = []
    for cos_sim, rec in scored[:limit]:
        sim_pct = round(max(0.0, min(100.0, cos_sim * 100.0)), 1)
        results.append(
            {
                "cycle_id": str(rec["cycle_id"]),
                "color": str(rec["color"]),
                "defect_label": str(rec["defect_label"]),
                "action": str(rec["action"]),
                "similarity_pct": float(sim_pct),
                "anomaly_score": float(rec["anomaly_score"]),
            }
        )
    return results


def _lookup_memory_record(cycle_id: str) -> Optional[dict[str, Any]]:
    alt_id = f"CYC-{cycle_id}" if not cycle_id.startswith("CYC-") else cycle_id
    with _memory_lock:
        for rec in _memory_records:
            if rec.get("cycle_id") == cycle_id:
                return dict(rec)
        if alt_id != cycle_id:
            for rec in _memory_records:
                if rec.get("cycle_id") == alt_id:
                    return dict(rec)
    return None


def _open_pymysql_connection(cfg: dict[str, Any], include_db: bool = True) -> Any:
    connect_kwargs: dict[str, Any] = {
        "host": cfg["host"],
        "port": cfg["port"],
        "user": cfg["user"],
        "password": cfg["password"],
        "charset": "utf8mb4",
        "autocommit": True,
        "connect_timeout": 6,
        "read_timeout": 8,
        "write_timeout": 8,
        "cursorclass": pymysql.cursors.DictCursor,
    }
    if include_db and cfg.get("database"):
        connect_kwargs["database"] = cfg["database"]
    if cfg.get("ssl") is not None:
        connect_kwargs["ssl"] = cfg["ssl"]
    return pymysql.connect(**connect_kwargs)


def _connect_and_ensure_schema(cfg: dict[str, Any]) -> Any:
    """
    Opens a PyMySQL connection to MariaDB 11.7+ and ensures `inspection_cycles`
    with `VECTOR(512)` and `VECTOR INDEX` (`M=8 DISTANCE=cosine`) exists.
    """
    global _schema_initialized_key
    target_key = (str(cfg["host"]), int(cfg["port"]), str(cfg["database"]))

    try:
        conn = _open_pymysql_connection(cfg, include_db=True)
    except Exception as exc:
        # Error 1049: Unknown database -> create if permitted, then reconnect
        err_code = exc.args[0] if getattr(exc, "args", None) else None
        safe_db = str(cfg.get("database") or DEFAULT_DATABASE)
        if err_code == 1049 and re.fullmatch(r"[A-Za-z0-9_]+", safe_db):
            bootstrap_conn = _open_pymysql_connection(cfg, include_db=False)
            try:
                with bootstrap_conn.cursor() as cur:
                    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{safe_db}`")
            finally:
                bootstrap_conn.close()
            conn = _open_pymysql_connection(cfg, include_db=True)
        else:
            raise

    with _db_lock:
        needs_init = (_schema_initialized_key != target_key) or (not _db_live)

    if needs_init:
        try:
            with conn.cursor() as cur:
                cur.execute("SHOW TABLES LIKE 'inspection_cycles'")
                if not cur.fetchone():
                    try:
                        cur.execute(_CREATE_TABLE_SQL)
                    except Exception as ddl_exc:
                        ddl_code = ddl_exc.args[0] if getattr(ddl_exc, "args", None) else None
                        if ddl_code == 1064:
                            cur.execute(_CREATE_TABLE_FALLBACK_SQL)
                        elif ddl_code != 1050:
                            raise
                cur.execute("SHOW TABLES LIKE 'sorting_policies'")
                if not cur.fetchone():
                    try:
                        cur.execute(_CREATE_POLICIES_TABLE_SQL)
                    except Exception as pol_exc:
                        pol_code = pol_exc.args[0] if getattr(pol_exc, "args", None) else None
                        if pol_code != 1050:
                            raise
            with _db_lock:
                _schema_initialized_key = target_key
        except Exception:
            conn.close()
            raise

    return conn


def _format_db_neighbor_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for row in rows:
        dist_raw = row.get("dist")
        dist = float(dist_raw) if dist_raw is not None else 1.0
        similarity_pct = round(max(0.0, min(100.0, (1.0 - dist) * 100.0)), 1)
        matches.append(
            {
                "cycle_id": str(row.get("cycle_id") or ""),
                "color": str(row.get("color") or "blue"),
                "defect_label": str(row.get("defect_label") or "None (Pristine)"),
                "action": str(row.get("action") or "PERFECT_BOWL"),
                "similarity_pct": float(similarity_pct),
                "anomaly_score": float(row.get("anomaly_score") if row.get("anomaly_score") is not None else 0.0),
            }
        )
    return matches


def _db_record_and_query_sync(
    cfg: dict[str, Any],
    row_params: dict[str, Any],
    vec_text: str,
    top_k: int,
) -> list[dict[str, Any]]:
    conn = _connect_and_ensure_schema(cfg)
    try:
        matches: list[dict[str, Any]] = []
        limit = max(0, int(top_k))
        with conn.cursor() as cur:
            if limit > 0:
                cur.execute(_FIND_SIMILAR_SQL, (vec_text, row_params["cycle_id"], limit))
                rows = cur.fetchall() or []
                matches = _format_db_neighbor_rows(list(rows))

            cur.execute(
                _UPSERT_CYCLE_SQL,
                (
                    row_params["cycle_id"],
                    row_params["color"],
                    row_params["defect_label"],
                    row_params["anomaly_score"],
                    row_params["action"],
                    row_params["npu_ms"],
                    row_params["igpu_ms"],
                    row_params["cpu_ms"],
                    row_params["total_ms"],
                    row_params["raw_url"],
                    row_params["composite_url"],
                    row_params["nemotron_reasoning"],
                    vec_text,
                ),
            )
        return matches
    finally:
        conn.close()


def _db_find_similar_by_id_sync(
    cfg: dict[str, Any],
    cycle_id: str,
    top_k: int,
    fallback_vec_text: Optional[str] = None,
) -> Optional[list[dict[str, Any]]]:
    conn = _connect_and_ensure_schema(cfg)
    try:
        limit = max(0, int(top_k))
        if limit == 0:
            return []

        target_id = cycle_id
        vec_text: Optional[str] = None

        with conn.cursor() as cur:
            cur.execute(_FETCH_CYCLE_EMBEDDING_SQL, (cycle_id,))
            row = cur.fetchone()
            if (not row or not row.get("vec_text")) and not cycle_id.startswith("CYC-"):
                alt_id = f"CYC-{cycle_id}"
                cur.execute(_FETCH_CYCLE_EMBEDDING_SQL, (alt_id,))
                alt_row = cur.fetchone()
                if alt_row and alt_row.get("vec_text"):
                    row = alt_row
                    target_id = alt_id

            if row and row.get("vec_text"):
                vec_text = str(row["vec_text"])
            elif fallback_vec_text:
                vec_text = fallback_vec_text
            else:
                return None

            cur.execute(_FIND_SIMILAR_SQL, (vec_text, target_id, limit))
            rows = cur.fetchall() or []
            return _format_db_neighbor_rows(list(rows))
    finally:
        conn.close()


async def record_cycle_and_find_similar(
    cycle: dict[str, Any],
    embedding: list[float] | None = None,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """
    Computes (or normalizes) the 512-dim brick embedding for `cycle`, updates the
    200-entry in-memory store, persists telemetry + `VECTOR(512)` to MariaDB 11.7+
    when configured, and returns top-`top_k` similar past cycles.
    """
    global _db_live

    raw_cycle_id = cycle.get("cycle_id") or (
        f"CYC-{cycle['brick_uuid']}" if cycle.get("brick_uuid") else f"CYC-{uuid.uuid4().hex[:8]}"
    )
    cycle_id = str(raw_cycle_id)[:64]
    color = str(cycle.get("color") or "blue")[:32]
    defect_label = str(cycle.get("defect_label") or "None (Pristine)")[:128]
    action = str(cycle.get("action") or "PERFECT_BOWL")[:32]

    try:
        anomaly_score = float(cycle.get("anomaly_score") if cycle.get("anomaly_score") is not None else 0.0)
        if not math.isfinite(anomaly_score):
            anomaly_score = 0.0
    except (TypeError, ValueError):
        anomaly_score = 0.0

    if embedding is not None and len(embedding) == EMBEDDING_DIM:
        vec_512 = _l2_normalize_512(list(embedding))
    else:
        raw_image_source = (
            cycle.get("raw_image_data")
            or cycle.get("raw_image_b64")
            or cycle.get("raw_url")
        )
        vec_512 = compute_brick_embedding(
            raw_image_data=raw_image_source,
            color=color,
            defect_label=defect_label,
            anomaly_score=anomaly_score,
        )

    # Always maintain in-memory fallback store (capped at 200 entries)
    _upsert_memory_record(
        cycle_id=cycle_id,
        color=color,
        defect_label=defect_label,
        action=action,
        anomaly_score=anomaly_score,
        embedding=vec_512,
    )

    latencies = cycle.get("latencies")
    lat_dict = latencies if isinstance(latencies, dict) else {}

    def _safe_float(val: Any, default: float = 0.0) -> float:
        try:
            f = float(val) if val is not None else default
            return f if math.isfinite(f) else default
        except (TypeError, ValueError):
            return default

    npu_ms = _safe_float(
        lat_dict.get("npu_ms", lat_dict.get("npu_anomalib_ms", cycle.get("npu_ms", cycle.get("npu_latency_ms")))),
        0.0,
    )
    igpu_ms = _safe_float(
        lat_dict.get("igpu_ms", lat_dict.get("igpu_vla_ms", cycle.get("igpu_ms", cycle.get("igpu_latency_ms")))),
        0.0,
    )
    cpu_ms = _safe_float(
        lat_dict.get("cpu_ms", lat_dict.get("cpu_control_ms", cycle.get("cpu_ms", cycle.get("cpu_latency_ms")))),
        0.0,
    )
    total_ms = _safe_float(
        lat_dict.get("total_ms", cycle.get("total_ms")),
        round(npu_ms + igpu_ms + cpu_ms, 2),
    )

    row_params = {
        "cycle_id": cycle_id,
        "color": color,
        "defect_label": defect_label,
        "anomaly_score": anomaly_score,
        "action": action,
        "npu_ms": npu_ms,
        "igpu_ms": igpu_ms,
        "cpu_ms": cpu_ms,
        "total_ms": total_ms,
        "raw_url": str(cycle.get("raw_url") or ""),
        "composite_url": str(cycle.get("composite_url") or cycle.get("heatmap_url") or ""),
        "nemotron_reasoning": str(cycle.get("nemotron_reasoning") or cycle.get("root_cause_reasoning") or ""),
    }

    cfg = _parse_db_config()
    if cfg is not None and _PYMYSQL_AVAILABLE:
        vec_text = json.dumps(vec_512)
        try:
            db_matches = await asyncio.to_thread(
                _db_record_and_query_sync,
                cfg,
                row_params,
                vec_text,
                top_k,
            )
            _db_live = True
            return db_matches
        except Exception as exc:
            _db_live = False
            logger.warning(
                "MariaDB vector store operation failed (%s); falling back to in-memory VECTOR(512).",
                type(exc).__name__,
            )
    else:
        _db_live = False

    return _memory_find_similar(vec_512, exclude_cycle_id=cycle_id, top_k=top_k)


async def find_similar_for_cycle_id(cycle_id: str, top_k: int = 3) -> list[dict[str, Any]]:
    """
    Looks up `cycle_id`'s stored 512-dim embedding (in MariaDB 11.7+ or in-memory store)
    and returns top-`top_k` nearest neighbor cycles, or `[]` if `cycle_id` is unknown.
    """
    global _db_live

    if not cycle_id or not str(cycle_id).strip():
        return []
    clean_id = str(cycle_id).strip()

    mem_rec = _lookup_memory_record(clean_id)
    fallback_vec_text = json.dumps(mem_rec["embedding"]) if mem_rec and mem_rec.get("embedding") else None
    resolved_mem_id = str(mem_rec["cycle_id"]) if mem_rec else clean_id

    cfg = _parse_db_config()
    if cfg is not None and _PYMYSQL_AVAILABLE:
        try:
            db_matches = await asyncio.to_thread(
                _db_find_similar_by_id_sync,
                cfg,
                resolved_mem_id,
                top_k,
                fallback_vec_text,
            )
            _db_live = True
            if db_matches is None:
                return []
            if db_matches or mem_rec is None:
                return db_matches
        except Exception as exc:
            _db_live = False
            logger.warning(
                "MariaDB similarity lookup failed (%s); falling back to in-memory VECTOR(512).",
                type(exc).__name__,
            )
    else:
        _db_live = False

    if mem_rec is None or not mem_rec.get("embedding"):
        return []

    return _memory_find_similar(
        mem_rec["embedding"],
        exclude_cycle_id=str(mem_rec["cycle_id"]),
        top_k=top_k,
    )


def _record_memory_policy_event(entry: dict[str, Any]) -> None:
    import datetime

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    with _memory_lock:
        for existing in _memory_policy_history:
            if existing.get("policy_id") == entry["policy_id"] and existing.get("is_current"):
                existing["valid_to"] = now_str
                existing["is_current"] = False
        _memory_policy_history.insert(
            0,
            {
                **entry,
                "valid_from": now_str,
                "valid_to": None,
                "is_current": True,
            },
        )
        if len(_memory_policy_history) > MEMORY_CAP:
            del _memory_policy_history[MEMORY_CAP:]


def _db_record_policy_sync(cfg: dict[str, Any], params: tuple[Any, ...]) -> None:
    conn = _connect_and_ensure_schema(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(_UPSERT_POLICY_SQL, params)
    finally:
        conn.close()


def _db_query_policy_history_sync(cfg: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    conn = _connect_and_ensure_schema(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(_QUERY_POLICY_HISTORY_SQL, (max(1, min(int(limit), 200)),))
            rows = cur.fetchall() or []
            history: list[dict[str, Any]] = []
            for r in rows:
                history.append(
                    {
                        "policy_id": str(r.get("policy_id") or ""),
                        "source": str(r.get("source") or ""),
                        "event_type": str(r.get("event_type") or ""),
                        "target_brick_color": str(r.get("target_brick_color") or "any"),
                        "defect_description": str(r.get("defect_description") or ""),
                        "action_on_match": str(r.get("action_on_match") or ""),
                        "anomaly_threshold": round(float(r.get("anomaly_threshold") or 0.55), 4),
                        "active_global_threshold": round(float(r.get("active_global_threshold") or 0.55), 4),
                        "is_active": bool(r.get("is_active")),
                        "reasoning": str(r.get("reasoning") or ""),
                        "valid_from": r.get("valid_from"),
                        "valid_to": r.get("valid_to"),
                        "is_current": bool(r.get("is_current")),
                    }
                )
            return history
    finally:
        conn.close()


async def record_policy_change(
    policy_id: str,
    source: str,
    event_type: str,
    anomaly_threshold: float,
    active_global_threshold: float,
    target_brick_color: str = "any",
    defect_description: str = "",
    action_on_match: str = "DEFECTIVE_BOWL",
    is_active: bool = True,
    reasoning: str = "",
) -> bool:
    """
    Logs a sorting rule mutation or dynamic threshold update into MariaDB's
    temporal `sorting_policies` (`WITH SYSTEM VERSIONING`) table, preserving full
    point-in-time `FOR SYSTEM_TIME ALL` history (plus in-memory fallback).
    """
    global _db_live

    clean_entry = {
        "policy_id": str(policy_id or "global_anomaly_threshold")[:64],
        "source": str(source or "system")[:32],
        "event_type": str(event_type or "POLICY_UPDATED")[:32],
        "target_brick_color": str(target_brick_color or "any")[:32],
        "defect_description": str(defect_description or "")[:255],
        "action_on_match": str(action_on_match or "DEFECTIVE_BOWL")[:32],
        "anomaly_threshold": round(float(anomaly_threshold), 4),
        "active_global_threshold": round(float(active_global_threshold), 4),
        "is_active": bool(is_active),
        "reasoning": str(reasoning or ""),
    }
    _record_memory_policy_event(clean_entry)

    cfg = _parse_db_config()
    if cfg is not None and _PYMYSQL_AVAILABLE:
        params = (
            clean_entry["policy_id"],
            clean_entry["source"],
            clean_entry["event_type"],
            clean_entry["target_brick_color"],
            clean_entry["defect_description"],
            clean_entry["action_on_match"],
            clean_entry["anomaly_threshold"],
            clean_entry["active_global_threshold"],
            1 if clean_entry["is_active"] else 0,
            clean_entry["reasoning"],
        )
        try:
            await asyncio.to_thread(_db_record_policy_sync, cfg, params)
            _db_live = True
            return True
        except Exception as exc:
            _db_live = False
            logger.warning(
                "MariaDB temporal policy write failed (%s); recorded in memory.",
                type(exc).__name__,
            )
    return False


async def get_policy_history(limit: int = 50) -> dict[str, Any]:
    """
    Queries `SELECT ... FROM sorting_policies FOR SYSTEM_TIME ALL` in MariaDB 11.7+
    to return the full temporal audit trail of Gemini Copilot rules and Nemotron
    threshold calibrations (with seamless in-memory fallback).
    """
    global _db_live

    clamped_limit = max(1, min(int(limit), 200))
    cfg = _parse_db_config()
    if cfg is not None and _PYMYSQL_AVAILABLE:
        try:
            rows = await asyncio.to_thread(_db_query_policy_history_sync, cfg, clamped_limit)
            _db_live = True
            return {
                "provider": "LIVE",
                "feature": "MariaDB WITH SYSTEM VERSIONING (FOR SYSTEM_TIME ALL)",
                "count": len(rows),
                "history": rows,
            }
        except Exception as exc:
            _db_live = False
            logger.warning(
                "MariaDB temporal history query failed (%s); using in-memory fallback.",
                type(exc).__name__,
            )

    with _memory_lock:
        fallback_rows = [dict(item) for item in _memory_policy_history[:clamped_limit]]
    return {
        "provider": "FALLBACK",
        "feature": "In-memory temporal policy log",
        "count": len(fallback_rows),
        "history": fallback_rows,
    }


def get_mariadb_status() -> dict[str, Any]:
    """
    Returns current MariaDB 11.7+ vector + temporal store configuration and liveness status.
    """
    configured = _parse_db_config() is not None
    live = bool(configured and _PYMYSQL_AVAILABLE and _db_live)
    if live:
        return {
            "configured": True,
            "live": True,
            "mode": "LIVE",
            "detail": "MariaDB 11.8 VECTOR(512) + SYSTEM VERSIONING",
        }
    return {
        "configured": configured,
        "live": False,
        "mode": "FALLBACK",
        "detail": "In-memory VECTOR(512) cosine",
    }
