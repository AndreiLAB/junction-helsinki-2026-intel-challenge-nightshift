import os
import io
import base64
import logging
from typing import Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFilter
from dotenv import load_dotenv

# Resolve the backend configuration independently of the process working directory.
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"), override=False)

logger = logging.getLogger("cloudinary_media")

# Check if Cloudinary is configured
cloudinary_url = os.environ.get("CLOUDINARY_URL", "").strip()
cloudinary_enabled = False

if cloudinary_url and "cloudinary://" in cloudinary_url and "api_key" not in cloudinary_url:
    try:
        import cloudinary
        import cloudinary.uploader
        from cloudinary import CloudinaryImage

        cloudinary.config(secure=True)
        cloudinary_enabled = True
        logger.info("Cloudinary configured successfully.")
    except Exception as e:
        logger.warning(f"Failed to initialize Cloudinary: {e}. Falling back to local data-URI pipeline.")
        cloudinary_enabled = False
else:
    logger.info("CLOUDINARY_URL not provided or contains placeholder. Using local simulation pipeline.")


def create_simulated_brick_image(
    color: str = "blue",
    defect_type: Optional[str] = None,
    is_defective: bool = False,
    score: float = 0.15
) -> tuple[str, str, str]:
    """
    Generates three base64 Data URIs:
    1. Raw inspection crop (512x512) with realistic Duplo studs and optional defect
    2. Anomalib heatmap mask (512x512) showing localized heat signature
    3. Composite heatmap overlay (45% opacity blend)
    """
    width, height = 512, 512

    # Map color names to RGB
    color_palette = {
        "blue": ((30, 115, 230), (15, 75, 175)),
        "yellow": ((245, 195, 30), (190, 145, 10)),
        "red": ((225, 45, 45), (160, 20, 20)),
        "green": ((35, 180, 85), (20, 120, 50)),
        "orange": ((245, 120, 25), (180, 80, 10)),
    }
    bg_color, edge_color = color_palette.get(color.lower(), ((30, 115, 230), (15, 75, 175)))

    # --- 1. Raw Image ---
    raw_img = Image.new("RGBA", (width, height), (15, 23, 42, 255)) # Dark slate studio backdrop
    draw = ImageDraw.Draw(raw_img)

    # Grid background / turntable marks
    for i in range(40, width, 60):
        draw.line([(i, 0), (i, height)], fill=(30, 41, 59, 120), width=1)
        draw.line([(0, i), (width, i)], fill=(30, 41, 59, 120), width=1)

    # Brick body (isometric / top-down perspective Duplo 2x2 brick)
    bx0, by0, bx1, by1 = 110, 110, 402, 402
    draw.rounded_rectangle([bx0, by0, bx1, by1], radius=16, fill=bg_color, outline=edge_color, width=4)

    # Duplo studs (4 circular studs with 3D bevel)
    stud_centers = [
        (185, 185), (327, 185),
        (185, 327), (327, 327)
    ]
    stud_r = 46

    for cx, cy in stud_centers:
        # Stud shadow
        draw.ellipse([cx - stud_r + 3, cy - stud_r + 4, cx + stud_r + 3, cy + stud_r + 4], fill=(0, 0, 0, 70))
        # Stud body
        draw.ellipse([cx - stud_r, cy - stud_r, cx + stud_r, cy + stud_r], fill=bg_color, outline=edge_color, width=3)
        # Stud highlight
        draw.arc([cx - stud_r + 4, cy - stud_r + 4, cx + stud_r - 4, cy + stud_r - 4], start=180, end=320, fill=(255, 255, 255, 180), width=3)

    # Draw defect if present
    defect_center = (327, 185) # Top-right stud region default
    if is_defective:
        if defect_type and "scratch" in defect_type.lower():
            # Dark scratch with white jagged highlight
            scratch_coords = [(280, 170), (310, 185), (345, 175), (370, 205)]
            draw.line(scratch_coords, fill=(20, 20, 20, 240), width=4)
            draw.line([(x+1, y+1) for x, y in scratch_coords], fill=(255, 255, 255, 150), width=1)
            defect_center = (325, 185)
        elif defect_type and "crack" in defect_type.lower():
            # Fracture line across body
            fracture = [(180, 230), (220, 255), (260, 245), (310, 280), (330, 310)]
            draw.line(fracture, fill=(10, 10, 10, 250), width=5)
            draw.line([(x+1, y+1) for x, y in fracture], fill=(255, 255, 255, 200), width=2)
            defect_center = (250, 260)
        elif defect_type and "chip" in defect_type.lower():
            # Chipped corner
            draw.polygon([(360, 110), (402, 110), (402, 160), (375, 135)], fill=(15, 23, 42, 255))
            draw.line([(360, 110), (375, 135), (402, 160)], fill=(255, 255, 255, 220), width=3)
            defect_center = (385, 130)
        else:
            # Dark side discoloration or grease mark
            draw.ellipse([300, 160, 360, 215], fill=(30, 20, 20, 180), outline=(200, 30, 30, 220), width=2)
            defect_center = (330, 185)

    # Calibration crosshairs & telemetry overlay in corner
    draw.line([(256 - 15, 256), (256 + 15, 256)], fill=(0, 199, 253, 160), width=1)
    draw.line([(256, 256 - 15), (256, 256 + 15)], fill=(0, 199, 253, 160), width=1)

    # --- 2. Anomalib Heatmap Mask ---
    heat_img = Image.new("RGBA", (width, height), (0, 0, 40, 255)) # Dark navy base
    heat_draw = ImageDraw.Draw(heat_img)

    if is_defective or score > 0.35:
        # Generate heat blob with smooth gaussian gradients
        hx, hy = defect_center
        # Multi-tiered heat radii (JET style: blue -> green -> yellow -> red)
        heat_draw.ellipse([hx - 140, hy - 140, hx + 140, hy + 140], fill=(0, 80, 255, 120))
        heat_draw.ellipse([hx - 95, hy - 95, hx + 95, hy + 95], fill=(0, 220, 120, 180))
        heat_draw.ellipse([hx - 60, hy - 60, hx + 60, hy + 60], fill=(255, 230, 0, 220))
        heat_draw.ellipse([hx - 30, hy - 30, hx + 30, hy + 30], fill=(255, 20, 20, 250))
        heat_img = heat_img.filter(ImageFilter.GaussianBlur(radius=18))
    else:
        # Low background noise heat
        heat_draw.ellipse([230, 230, 280, 280], fill=(0, 60, 160, 70))
        heat_img = heat_img.filter(ImageFilter.GaussianBlur(radius=25))

    # --- 3. Composite Heatmap Overlay ---
    composite = raw_img.convert("RGBA").copy()
    # Blend 45% heatmap over raw
    alpha_heat = heat_img.copy()
    # Modulate alpha to ~45% (115/255)
    r, g, b, a = alpha_heat.split()
    a = a.point(lambda p: int(p * 0.45))
    alpha_heat.putalpha(a)
    composite.paste(alpha_heat, (0, 0), alpha_heat)

    # Convert to Data URIs
    def to_data_uri(img: Image.Image) -> str:
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{b64}"

    return to_data_uri(raw_img), to_data_uri(heat_img), to_data_uri(composite)


def _is_valid_upload_source(data: bytes | str | None) -> bool:
    if data is None:
        return False
    if isinstance(data, bytes):
        return len(data) > 0
    if isinstance(data, str):
        s = data.strip()
        return (
            s.startswith("data:image/")
            or s.startswith("http://")
            or s.startswith("https://")
            or os.path.isfile(s)
        )
    return False


def upload_inspection_with_heatmap(
    brick_uuid: str,
    raw_image_data: bytes | str,
    heatmap_image_data: bytes | str,
    defect_label: str,
    score: float,
    color: str = "blue",
) -> Dict[str, str]:
    """
    Uploads raw inspection crop and Anomalib heatmap mask to Cloudinary,
    returning an auto-composited overlay URL (`l_overlay`).
    Gracefully falls back to high-fidelity simulated Data URIs if Cloudinary is not configured.
    """
    global cloudinary_enabled

    # Generate high-res simulation URIs (used as fallback or when caller passes synthetic placeholder IDs)
    is_defective = score > 0.40 or (
        "perfect" not in defect_label.lower() and "pristine" not in defect_label.lower()
    )
    raw_uri, heat_uri, comp_uri = create_simulated_brick_image(
        color=color,
        defect_type=defect_label,
        is_defective=is_defective,
        score=score,
    )

    # Keep server lifespan seed cycles instant without blocking startup on network I/O
    if str(brick_uuid).startswith("init_"):
        return {
            "raw_url": raw_uri,
            "heatmap_url": heat_uri,
            "composite_heatmap_url": comp_uri,
            "provider": "local_synthesizer",
        }

    if cloudinary_enabled:
        try:
            import cloudinary.uploader
            from cloudinary import CloudinaryImage

            raw_source = raw_image_data if _is_valid_upload_source(raw_image_data) else raw_uri
            heat_source = heatmap_image_data if _is_valid_upload_source(heatmap_image_data) else heat_uri

            # Upload raw image
            raw_res = cloudinary.uploader.upload(
                raw_source,
                public_id=f"junction2026/raw_{brick_uuid}",
                tags=["junction2026", defect_label],
                overwrite=True,
            )

            # Upload heatmap mask
            heat_id = f"junction2026/heat_{brick_uuid}"
            heat_res = cloudinary.uploader.upload(
                heat_source,
                public_id=heat_id,
                overwrite=True,
            )

            # Composite semi-transparent heatmap overlay onto raw inspection crop
            overlay_layer = heat_id.replace("/", ":")
            composite_url = CloudinaryImage(f"junction2026/raw_{brick_uuid}").build_url(
                transformation=[
                    {"width": 512, "height": 512, "crop": "fill"},
                    {"overlay": overlay_layer, "opacity": 45, "width": 512, "height": 512, "crop": "fill"},
                    {"flags": "layer_apply"},
                ]
            )

            return {
                "raw_url": raw_res.get("secure_url", raw_uri),
                "heatmap_url": heat_res.get("secure_url", heat_uri),
                "composite_heatmap_url": composite_url or comp_uri,
                "provider": "cloudinary",
            }
        except Exception as e:
            logger.error(f"Cloudinary upload failed ({type(e).__name__}). Falling back to simulation.")

    return {
        "raw_url": raw_uri,
        "heatmap_url": heat_uri,
        "composite_heatmap_url": comp_uri,
        "provider": "local_synthesizer",
    }
