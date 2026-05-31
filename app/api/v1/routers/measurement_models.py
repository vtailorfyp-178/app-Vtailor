"""Measurement 3D mannequin model — Cloudinary upload + MongoDB catalog."""

from __future__ import annotations

import io
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.db.mongodb import check_mongo_connection, get_database

router = APIRouter(prefix="/measurement-models", tags=["Measurement Models"])

COLLECTION = "measurement_3d_models"
DEFAULT_NAME = "measurement-model"
_cloudinary_ready = False


def _load_models_service_env() -> dict[str, str]:
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
                "CLOUDINARY_API_SECRET to app-Vtailor/.env."
            ),
        )

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
    )
    _cloudinary_ready = True


def _sanitize_name(raw: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]", "-", str(raw or DEFAULT_NAME).strip())[:64]
    return value or DEFAULT_NAME


async def _upsert_model_doc(doc: dict) -> dict | None:
    try:
        if not await check_mongo_connection():
            return None
        db = get_database()
        name = doc["name"]
        await db[COLLECTION].update_one(
            {"name": name, "type": "measurement"},
            {"$set": doc},
            upsert=True,
        )
        saved = await db[COLLECTION].find_one({"name": name, "type": "measurement"})
        return saved
    except Exception as exc:
        print(f"[measurement-models] MongoDB save skipped: {exc}")
        return None


def _serialize_doc(doc: dict) -> dict:
    created = doc.get("createdAt")
    if isinstance(created, datetime):
        created_iso = created.isoformat()
    else:
        created_iso = created
    return {
        "id": str(doc.get("_id", "")),
        "name": doc.get("name", DEFAULT_NAME),
        "type": doc.get("type", "measurement"),
        "modelUrl": doc.get("modelUrl", ""),
        "publicId": doc.get("publicId", ""),
        "createdAt": created_iso,
    }


class SaveMeasurementModelBody(BaseModel):
    name: str = Field(default=DEFAULT_NAME, min_length=1, max_length=64)
    modelUrl: str = Field(..., min_length=8)
    publicId: str | None = None


@router.get("/ping")
async def measurement_models_ping():
    return {"ok": True, "fetch": "/app/api/v1/measurement-models/measurement-model"}


@router.post("/upload")
async def upload_measurement_model(
    file: UploadFile = File(...),
    name: str = Form(DEFAULT_NAME),
):
    """Upload optimized measurement-model.glb to Cloudinary and persist URL in MongoDB."""
    _ensure_cloudinary()
    settings = get_settings()

    filename = (file.filename or "").lower()
    if not filename.endswith(".glb"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .glb files are allowed.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file.")
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="GLB too large (max 20 MB). Run compress:measurement-model first.",
        )

    model_name = _sanitize_name(name)
    folder = f"{settings.CLOUDINARY_BASE_FOLDER}/measurement-models"
    public_id = model_name

    try:
        import cloudinary.uploader

        result = cloudinary.uploader.upload(
            io.BytesIO(content),
            resource_type="raw",
            folder=folder,
            public_id=public_id,
            overwrite=True,
        )
    except Exception as exc:
        print(f"[measurement-models] Cloudinary upload failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Cloudinary upload failed: {exc}",
        ) from exc

    model_url = result.get("secure_url") or result.get("url")
    if not model_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Cloudinary upload did not return a URL.",
        )

    created_at = datetime.now(timezone.utc)
    doc = {
        "name": model_name,
        "type": "measurement",
        "modelUrl": model_url,
        "publicId": result.get("public_id") or public_id,
        "createdAt": created_at,
    }
    saved = await _upsert_model_doc(doc)
    payload = _serialize_doc(saved or doc)
    return payload


@router.post("/save")
async def save_measurement_model_url(body: SaveMeasurementModelBody):
    """Persist an existing Cloudinary (or CDN) URL for the measurement model."""
    model_name = _sanitize_name(body.name)
    created_at = datetime.now(timezone.utc)
    doc = {
        "name": model_name,
        "type": "measurement",
        "modelUrl": body.modelUrl.strip(),
        "publicId": (body.publicId or "").strip(),
        "createdAt": created_at,
    }
    saved = await _upsert_model_doc(doc)
    return _serialize_doc(saved or doc)


@router.get("/{model_name}")
async def fetch_measurement_model(model_name: str = DEFAULT_NAME):
    """Return the active measurement 3D model URL."""
    name = _sanitize_name(model_name)

    try:
        if await check_mongo_connection():
            db = get_database()
            doc = await db[COLLECTION].find_one({"name": name, "type": "measurement"})
            if doc and doc.get("modelUrl"):
                return _serialize_doc(doc)
    except Exception as exc:
        print(f"[measurement-models] MongoDB fetch skipped: {exc}")

    return {
        "id": "",
        "name": name,
        "type": "measurement",
        "modelUrl": "",
        "publicId": "",
        "createdAt": None,
        "fallback": True,
    }
