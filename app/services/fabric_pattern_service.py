"""Detect fabric repeat unit and build seamless swatch tiles for 3D texture mapping."""

from __future__ import annotations

import io
import secrets
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageChops, ImageStat


@dataclass
class FabricPatternMeta:
    repeat_period_x: int
    repeat_period_y: int
    tile_width: int
    tile_height: int
    motif_size_cm: float
    repeats_per_meter: float
    confidence: float
    source_width: int
    source_height: int
    tiles_across_source: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "repeatPeriodX": self.repeat_period_x,
            "repeatPeriodY": self.repeat_period_y,
            "tileWidth": self.tile_width,
            "tileHeight": self.tile_height,
            "motifSizeCm": round(self.motif_size_cm, 2),
            "repeatsPerMeter": round(self.repeats_per_meter, 2),
            "confidence": round(self.confidence, 3),
            "sourceWidth": self.source_width,
            "sourceHeight": self.source_height,
            "tilesAcrossSource": round(self.tiles_across_source, 2),
        }


def _best_repeat_lag(profile: list[float], min_lag: int, max_lag: int) -> tuple[int, float]:
    n = len(profile)
    if n < min_lag * 3:
        return max(min_lag, n // 3), 0.0

    max_lag = min(max_lag, n // 2)
    mean = sum(profile) / n
    var = sum((v - mean) ** 2 for v in profile) / max(n, 1)
    if var < 1e-6:
        return max(min_lag, n // 3), 0.0

    best_lag = min_lag
    best_score = -1.0
    for lag in range(min_lag, max_lag + 1):
        acc = 0.0
        count = 0
        for i in range(n - lag):
            acc += (profile[i] - mean) * (profile[i + lag] - mean)
            count += 1
        score = acc / (count * var) if count else 0.0
        if score > best_score:
            best_score = score
            best_lag = lag
    return best_lag, max(0.0, min(1.0, best_score))


def _edge_seam_score(tile: Image.Image) -> float:
    """Lower = better seamless tile."""
    tw, th = tile.size
    if tw < 8 or th < 8:
        return 999.0
    left = tile.crop((0, 0, 3, th))
    right = tile.crop((tw - 3, 0, tw, th))
    top = tile.crop((0, 0, tw, 3))
    bottom = tile.crop((0, th - 3, tw, th))
    return (
        ImageStat.Stat(ImageChops.difference(left, right)).mean[0]
        + ImageStat.Stat(ImageChops.difference(top, bottom)).mean[0]
    )


def _find_best_tile_origin(img: Image.Image, tw: int, th: int) -> tuple[int, int]:
    w, h = img.size
    if tw >= w or th >= h:
        return 0, 0

    best = (0, 0)
    best_diff = float("inf")
    step_x = max(1, tw // 10)
    step_y = max(1, th // 10)
    for ox in range(0, min(tw, w - tw), step_x):
        for oy in range(0, min(th, h - th), step_y):
            tile = img.crop((ox, oy, ox + tw, oy + th))
            diff = _edge_seam_score(tile)
            if diff < best_diff:
                best_diff = diff
                best = (ox, oy)
    return best


def _pick_tile_size(
    src: Image.Image,
    period_x: int,
    period_y: int,
    confidence: float,
    aw: int,
    ah: int,
) -> tuple[int, int, float]:
    """Choose repeat tile size — prefer smaller repeat for dense floral lawn."""
    source_w, source_h = src.size
    min_side = max(48, min(source_w, source_h) // 8)

    candidates: list[tuple[int, int, float]] = []

    ax = int(max(min_side, min(source_w, round(period_x * source_w / max(aw, 1)))))
    ay = int(max(min_side, min(source_h, round(period_y * source_h / max(ah, 1)))))
    candidates.append((ax, ay, confidence))

    # Common lawn repeat fractions (2–6 motifs across swatch photo)
    for div in (2, 3, 4, 5, 6, 7, 8):
        tw = max(min_side, source_w // div)
        th = max(min_side, source_h // div)
        ox, oy = _find_best_tile_origin(src, tw, th)
        tile = src.crop((ox, oy, ox + tw, oy + th))
        seam = _edge_seam_score(tile)
        # Prefer smaller tiles (more repeats) when seam quality is similar
        score = seam + (tw + th) * 0.002
        candidates.append((tw, th, max(0.2, 1.0 - score / 80.0)))

    candidates.sort(key=lambda c: (c[2] * -1, c[0] * c[1]))
    tw, th, conf = candidates[0]
    return tw, th, conf


def analyze_fabric_pattern(image_bytes: bytes) -> tuple[FabricPatternMeta, Image.Image, Image.Image]:
    src = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    source_w, source_h = src.size

    analysis = src.copy()
    analysis.thumbnail((512, 512), Image.Resampling.LANCZOS)
    aw, ah = analysis.size
    gray = analysis.convert("L")
    pixels = gray.load()

    row_profile = [sum(pixels[x, y] for x in range(aw)) / aw for y in range(ah)]
    col_profile = [sum(pixels[x, y] for y in range(ah)) / ah for x in range(aw)]

    min_lag = max(12, min(aw, ah) // 28)
    max_lag = min(aw, ah) // 2

    period_y, score_y = _best_repeat_lag(row_profile, min_lag, max_lag)
    period_x, score_x = _best_repeat_lag(col_profile, min_lag, max_lag)
    confidence = (score_x + score_y) / 2.0

    tw, th, pick_conf = _pick_tile_size(src, period_x, period_y, confidence, aw, ah)
    confidence = max(confidence, pick_conf)

    ox, oy = _find_best_tile_origin(src, tw, th)
    tile = src.crop((ox, oy, ox + tw, oy + th))

    max_edge = 512
    if max(tile.size) > max_edge:
        ratio = max_edge / max(tile.size)
        tile = tile.resize(
            (max(32, int(tile.width * ratio)), max(32, int(tile.height * ratio))),
            Image.Resampling.LANCZOS,
        )
    tw, th = tile.size

    tiles_across = max(1.0, source_w / max(tw, 1))
    # Phone fabric photo ≈ 40–50 cm of cloth visible
    assumed_swatch_cm = 45.0
    motif_cm = assumed_swatch_cm / tiles_across
    repeats_per_meter = 100.0 / max(motif_cm, 2.0)

    meta = FabricPatternMeta(
        repeat_period_x=period_x,
        repeat_period_y=period_y,
        tile_width=tw,
        tile_height=th,
        motif_size_cm=motif_cm,
        repeats_per_meter=repeats_per_meter,
        confidence=confidence,
        source_width=source_w,
        source_height=source_h,
        tiles_across_source=tiles_across,
    )

    grid = 6
    megatile = Image.new("RGB", (tw * grid, th * grid))
    for gy in range(grid):
        for gx in range(grid):
            megatile.paste(tile, (gx * tw, gy * th))

    return meta, tile, megatile


def tile_jpeg_bytes(img: Image.Image, quality: int = 90) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def build_tile_public_id(user_id: str, suffix: str = "tile") -> str:
    stamp = secrets.token_hex(4)
    return f"{user_id}_{suffix}_{stamp}"
