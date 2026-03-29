from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Dict

from app.core.security import get_current_active_user, require_admin
from app.core.limiter import limiter
from app.core.config import settings
from app.services.lxd_client import get_client

router = APIRouter(prefix="/api/v1/storage", tags=["Storage"])


class StoragePoolCreate(BaseModel):
    name: str
    driver: str = "dir"
    config: Dict = {}
    description: str = ""


class VolumeCreate(BaseModel):
    name: str
    type: str = "custom"
    config: Dict = {}


def _pool_to_dict(pool) -> dict:
    return {
        "name": pool.name,
        "driver": pool.driver,
        "description": getattr(pool, "description", ""),
        "config": dict(pool.config),
        "status": getattr(pool, "status", "Unknown"),
    }


@router.get("/pools", summary="List storage pools")
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def list_pools(request: Request, _=Depends(get_current_active_user)):
    client = get_client()
    return [_pool_to_dict(p) for p in client.storage_pools.all()]


@router.get("/pools/{pool_name}", summary="Get storage pool details")
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def get_pool(request: Request, pool_name: str, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        pool = client.storage_pools.get(pool_name)
        return _pool_to_dict(pool)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Storage pool '{pool_name}' not found")


@router.post("/pools", status_code=201, summary="Create a storage pool (admin only)")
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def create_pool(request: Request, data: StoragePoolCreate, _=Depends(require_admin)):
    client = get_client()
    try:
        pool = client.storage_pools.create({
            "name": data.name,
            "driver": data.driver,
            "config": data.config,
            "description": data.description,
        })
        return {"message": f"Storage pool '{data.name}' created", **_pool_to_dict(pool)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/pools/{pool_name}", summary="Delete a storage pool (admin only)")
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def delete_pool(request: Request, pool_name: str, _=Depends(require_admin)):
    client = get_client()
    try:
        pool = client.storage_pools.get(pool_name)
        pool.delete()
        return {"message": f"Storage pool '{pool_name}' deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/pools/{pool_name}/volumes", summary="List volumes in a pool")
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def list_volumes(request: Request, pool_name: str, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        pool = client.storage_pools.get(pool_name)
        volumes = pool.volumes.all()
        return [
            {
                "name": v.name,
                "type": v.type,
                "config": dict(v.config),
                "pool": pool_name,
            }
            for v in volumes
        ]
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/pools/{pool_name}/volumes", status_code=201, summary="Create a volume")
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def create_volume(request: Request, pool_name: str, data: VolumeCreate, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        pool = client.storage_pools.get(pool_name)
        pool.volumes.create({"name": data.name, "type": data.type, "config": data.config})
        return {"message": f"Volume '{data.name}' created in pool '{pool_name}'"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/pools/{pool_name}/volumes/{volume_type}/{volume_name}", summary="Delete a volume")
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def delete_volume(request: Request, pool_name: str, volume_type: str, volume_name: str, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        pool = client.storage_pools.get(pool_name)
        vol = pool.volumes.get(volume_type, volume_name)
        vol.delete()
        return {"message": f"Volume '{volume_name}' deleted from pool '{pool_name}'"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
