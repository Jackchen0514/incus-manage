from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Dict

from app.core.security import get_current_active_user, require_admin
from app.core.limiter import limiter
from app.core.config import settings
from app.services.lxd_client import get_client

router = APIRouter(prefix="/api/v1/profiles", tags=["Profiles"])


class ProfileCreate(BaseModel):
    name: str
    description: str = ""
    config: Dict = {}
    devices: Dict = {}


def _profile_to_dict(profile) -> dict:
    return {
        "name": profile.name,
        "description": getattr(profile, "description", ""),
        "config": dict(profile.config),
        "devices": dict(profile.devices),
    }


@router.get("", summary="List all profiles")
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def list_profiles(request: Request, _=Depends(get_current_active_user)):
    client = get_client()
    return [_profile_to_dict(p) for p in client.profiles.all()]


@router.get("/{name}", summary="Get profile details")
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def get_profile(request: Request, name: str, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        profile = client.profiles.get(name)
        return _profile_to_dict(profile)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Profile '{name}' not found")


@router.post("", status_code=201, summary="Create a profile (admin only)")
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def create_profile(request: Request, data: ProfileCreate, _=Depends(require_admin)):
    client = get_client()
    try:
        profile = client.profiles.create(
            data.name,
            config=data.config,
            devices=data.devices,
        )
        return {"message": f"Profile '{data.name}' created", **_profile_to_dict(profile)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{name}", summary="Update a profile (admin only)")
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def update_profile(request: Request, name: str, data: ProfileCreate, _=Depends(require_admin)):
    client = get_client()
    try:
        profile = client.profiles.get(name)
        profile.config = data.config
        profile.devices = data.devices
        profile.description = data.description
        profile.save()
        return {"message": f"Profile '{name}' updated", **_profile_to_dict(profile)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{name}", summary="Delete a profile (admin only)")
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def delete_profile(request: Request, name: str, _=Depends(require_admin)):
    client = get_client()
    try:
        profile = client.profiles.get(name)
        profile.delete()
        return {"message": f"Profile '{name}' deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
