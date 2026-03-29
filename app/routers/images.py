from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from app.core.security import get_current_active_user
from app.core.limiter import limiter
from app.core.config import settings
from app.services.lxd_client import get_client

router = APIRouter(prefix="/api/v1/images", tags=["Images"])


class ImageCopy(BaseModel):
    server: str = "https://images.linuxcontainers.org"
    alias: str
    local_alias: Optional[str] = None


def _image_to_dict(img) -> dict:
    aliases = [a["name"] for a in img.aliases] if img.aliases else []
    return {
        "fingerprint": img.fingerprint,
        "aliases": aliases,
        "architecture": img.architecture,
        "size": img.size,
        "upload_date": str(img.uploaded_at) if hasattr(img, "uploaded_at") else None,
        "properties": img.properties,
        "type": getattr(img, "type", "container"),
        "public": img.public,
    }


@router.get("", summary="List local images")
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def list_images(request: Request, _=Depends(get_current_active_user)):
    client = get_client()
    return [_image_to_dict(img) for img in client.images.all()]


@router.get("/{fingerprint}", summary="Get image by fingerprint")
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def get_image(request: Request, fingerprint: str, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        img = client.images.get(fingerprint)
        return _image_to_dict(img)
    except Exception:
        raise HTTPException(status_code=404, detail="Image not found")


@router.post("/copy", status_code=201, summary="Copy/download an image from a remote server")
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def copy_image(request: Request, data: ImageCopy, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        img = client.images.create_from_simplestreams(data.server, data.alias, wait=True)
        if data.local_alias:
            img.add_alias(data.local_alias, "")
        return {"message": "Image downloaded", "fingerprint": img.fingerprint, "aliases": [a["name"] for a in img.aliases]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{fingerprint}", summary="Delete a local image")
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def delete_image(request: Request, fingerprint: str, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        img = client.images.get(fingerprint)
        img.delete(wait=True)
        return {"message": f"Image '{fingerprint}' deleted"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
