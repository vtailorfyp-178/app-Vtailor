"""Fabric print upload — Cloudinary directly (no models-service proxy required)."""

from __future__ import annotations

import io
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status

from app.core.config import get_settings
from app.db.mongodb import check_mongo_connection, get_database
from app.services.fabric_pattern_service import (
    analyze_fabric_pattern,
    build_tile_public_id,
    tile_jpeg_bytes,
)

router = APIRouter(prefix="/fabric-prints", tags=["Fabric Prints"])

ALLOWED_MIME = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}
_cloudinary_ready = False


def _load_models_service_env() -> dict[str, str]:
    """Fallback: read Cloudinary keys from models-service/.env when main .env lacks them."""
    root = Path(__file__).resolve().parents[4]
    env_path = root / "models-service" / ".env"
    if not env_path.is_file():
        return {}

    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, raw = line.partition("=")
        values[key.strip()] = raw.strip().strip('"').strip("'")
    return values


def _ensure_cloudinary():
    global _cloudinary_ready
    if _cloudinary_ready:
        return

    try:
        import cloudinary
        import cloudinary.uploader
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Missing cloudinary package. Run: cd app-Vtailor && pip install cloudinary",
        ) from exc

    settings = get_settings()
    cloud_name = settings.CLOUDINARY_CLOUD_NAME
    api_key = settings.CLOUDINARY_API_KEY
    api_secret = settings.CLOUDINARY_API_SECRET

    if not (cloud_name and api_key and api_secret):
        fallback = _load_models_service_env()
        cloud_name = cloud_name or fallback.get("CLOUDINARY_CLOUD_NAME")
        api_key = api_key or fallback.get("CLOUDINARY_API_KEY")
        api_secret = api_secret or fallback.get("CLOUDINARY_API_SECRET")

    if not (cloud_name and api_key and api_secret):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Cloudinary not configured. Add CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, "
                "CLOUDINARY_API_SECRET to app-Vtailor/.env (copy from models-service/.env)."
            ),
        )

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
    )
    _cloudinary_ready = True


def _sanitize_user_id(raw: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]", "_", str(raw or "anonymous").strip())[:128]
    return value or "anonymous"


def _resolve_mime(content_type: str | None, filename: str | None) -> str | None:
    mime = (content_type or "").lower().split(";")[0].strip()
    if mime in ALLOWED_MIME:
        return mime
    if mime in ("", "application/octet-stream"):
        ext = Path(filename or "").suffix.lower()
        if ext in ALLOWED_EXT:
            return "image/jpeg" if ext in (".jpg", ".jpeg") else f"image/{ext.lstrip('.')}"
    return None


def _build_public_id(user_id: str) -> str:
    stamp = int(datetime.now(timezone.utc).timestamp() * 1000)
    rand = secrets.token_hex(4)
    return f"{user_id}_{stamp}_{rand}"


async def _save_to_mongo(doc: dict) -> dict | None:
    try:
        if not await check_mongo_connection():
            return None
        db = get_database()
        result = await db.custom_fabric_prints.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc
    except Exception as exc:
        print(f"[fabric-prints] MongoDB save skipped: {exc}")
        return None


@router.get("/ping")
async def fabric_prints_ping():
    return {"ok": True, "upload": "/app/api/v1/fabric-prints/upload"}


@router.post("/upload")
async def upload_fabric_print(
    file: UploadFile = File(...),
    userId: str = Form(...),
    printName: str | None = Form(None),
):
    _ensure_cloudinary()
    settings = get_settings()

    mime = _resolve_mime(file.content_type, file.filename)
    if not mime:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPG, JPEG, PNG, and WEBP images are allowed.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No image file provided.")
    if len(content) > settings.FABRIC_PRINT_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image too large (max {settings.FABRIC_PRINT_MAX_BYTES // (1024 * 1024)} MB).",
        )

    user_id = _sanitize_user_id(userId)
    name = (printName or file.filename or "Custom print").strip()[:120]
    folder = f"{settings.CLOUDINARY_BASE_FOLDER}/{settings.FABRIC_PRINTS_FOLDER}/{user_id}"
    public_id = _build_public_id(user_id)

    try:
        import cloudinary.uploader

        result = cloudinary.uploader.upload(
            io.BytesIO(content),
            resource_type="image",
            folder=folder,
            public_id=public_id,
            overwrite=True,
            quality="auto:good",
            fetch_format="auto",
        )
    except Exception as exc:
        print(f"[fabric-prints] Cloudinary upload failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Cloudinary upload failed: {exc}",
        ) from exc

    cloudinary_url = result.get("secure_url") or result.get("url")
    if not cloudinary_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Cloudinary upload did not return a URL.",
        )

    # Pattern analysis — extract repeat tile + megatile for accurate 3D mapping
    tile_url = cloudinary_url
    megatile_url = cloudinary_url
    pattern_meta: dict = {}
    try:
        meta, tile_img, megatile_img = analyze_fabric_pattern(content)
        pattern_meta = meta.as_dict()

        tile_bytes = tile_jpeg_bytes(tile_img, quality=92)
        megatile_bytes = tile_jpeg_bytes(megatile_img, quality=90)

        tile_result = cloudinary.uploader.upload(
            io.BytesIO(tile_bytes),
            resource_type="image",
            folder=f"{folder}/tiles",
            public_id=build_tile_public_id(user_id, "tile"),
            overwrite=True,
            quality="auto:good",
        )
        mega_result = cloudinary.uploader.upload(
            io.BytesIO(megatile_bytes),
            resource_type="image",
            folder=f"{folder}/tiles",
            public_id=build_tile_public_id(user_id, "mega"),
            overwrite=True,
            quality="auto:good",
        )
        tile_url = tile_result.get("secure_url") or tile_result.get("url") or tile_url
        megatile_url = mega_result.get("secure_url") or mega_result.get("url") or tile_url
    except Exception as exc:
        print(f"[fabric-prints] Pattern analysis skipped: {exc}")

    upload_date = datetime.now(timezone.utc)
    doc = {
        "userId": user_id,
        "printName": name,
        "printImage": file.filename or name,
        "cloudinaryUrl": cloudinary_url,
        "tileUrl": tile_url,
        "megatileUrl": megatile_url,
        "patternMeta": pattern_meta,
        "publicId": result.get("public_id") or public_id,
        "uploadDate": upload_date,
    }

    saved = await _save_to_mongo(doc)
    record_id = str(saved["_id"]) if saved and saved.get("_id") else public_id

    return {
        "id": record_id,
        "userId": user_id,
        "printName": name,
        "printImage": doc["printImage"],
        "cloudinaryUrl": cloudinary_url,
        "tileUrl": tile_url,
        "megatileUrl": megatile_url,
        "patternMeta": pattern_meta,
        "publicId": doc["publicId"],
        "uploadDate": upload_date.isoformat(),
    }


@router.get("")
async def list_fabric_prints(userId: str = Query(..., min_length=1)):
    user_id = _sanitize_user_id(userId)
    if user_id == "anonymous":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="userId is required.")

    try:
        if not await check_mongo_connection():
            return {"prints": []}
        db = get_database()
        cursor = (
            db.custom_fabric_prints.find({"userId": user_id})
            .sort("uploadDate", -1)
            .limit(40)
        )
        prints = []
        async for doc in cursor:
            prints.append(
                {
                    "id": str(doc["_id"]),
                    "userId": doc.get("userId", user_id),
                    "printName": doc.get("printName", ""),
                    "printImage": doc.get("printImage", ""),
                    "cloudinaryUrl": doc.get("cloudinaryUrl", ""),
                    "publicId": doc.get("publicId", ""),
                    "uploadDate": doc.get("uploadDate"),
                }
            )
        return {"prints": prints}
    except Exception as exc:
        print(f"[fabric-prints] MongoDB list skipped: {exc}")
        return {"prints": []}
