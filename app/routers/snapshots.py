from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from app.core.security import get_current_active_user
from app.core.limiter import limiter
from app.core.config import settings
from app.services.lxd_client import get_client

router = APIRouter(prefix="/api/v1/instances", tags=["Snapshots"])


class SnapshotCreate(BaseModel):
    name: str
    stateful: bool = False


@router.get("/{instance_name}/snapshots", summary="List snapshots of an instance")
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def list_snapshots(request: Request, instance_name: str, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        inst = client.instances.get(instance_name)
        snapshots = inst.snapshots.all()
        return [
            {
                "name": s.name,
                "created_at": str(s.created_at) if hasattr(s, "created_at") else None,
                "stateful": getattr(s, "stateful", False),
            }
            for s in snapshots
        ]
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{instance_name}/snapshots", status_code=201, summary="Create a snapshot")
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def create_snapshot(request: Request, instance_name: str, data: SnapshotCreate, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        inst = client.instances.get(instance_name)
        snap = inst.snapshots.create(data.name, stateful=data.stateful, wait=True)
        return {"message": f"Snapshot '{data.name}' created", "name": snap.name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{instance_name}/snapshots/{snapshot_name}/restore", summary="Restore a snapshot")
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def restore_snapshot(request: Request, instance_name: str, snapshot_name: str, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        inst = client.instances.get(instance_name)
        inst.restore_snapshot(snapshot_name, wait=True)
        return {"message": f"Snapshot '{snapshot_name}' restored to instance '{instance_name}'"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{instance_name}/snapshots/{snapshot_name}", summary="Delete a snapshot")
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def delete_snapshot(request: Request, instance_name: str, snapshot_name: str, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        inst = client.instances.get(instance_name)
        snap = inst.snapshots.get(snapshot_name)
        snap.delete(wait=True)
        return {"message": f"Snapshot '{snapshot_name}' deleted"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
