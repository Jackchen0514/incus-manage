from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Dict

from app.core.security import get_current_active_user, require_admin
from app.core.limiter import limiter
from app.core.config import settings
from app.services.lxd_client import get_client

router = APIRouter(prefix="/api/v1/networks", tags=["Networks"])


class NetworkCreate(BaseModel):
    name: str
    description: str = ""
    type: str = "bridge"
    config: Dict = {}


def _network_to_dict(net) -> dict:
    return {
        "name": net.name,
        "description": getattr(net, "description", ""),
        "type": net.type,
        "config": dict(net.config),
        "managed": net.managed,
        "status": net.status,
    }


@router.get("", summary="List all networks")
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def list_networks(request: Request, _=Depends(get_current_active_user)):
    client = get_client()
    return [_network_to_dict(n) for n in client.networks.all()]


@router.get("/{name}", summary="Get network details")
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def get_network(request: Request, name: str, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        net = client.networks.get(name)
        return _network_to_dict(net)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Network '{name}' not found")


@router.post("", status_code=201, summary="Create a network (admin only)")
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def create_network(request: Request, data: NetworkCreate, _=Depends(require_admin)):
    client = get_client()
    try:
        net = client.networks.create(
            data.name,
            description=data.description,
            type=data.type,
            config=data.config,
        )
        return {"message": f"Network '{data.name}' created", **_network_to_dict(net)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{name}", summary="Delete a network (admin only)")
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def delete_network(request: Request, name: str, _=Depends(require_admin)):
    client = get_client()
    try:
        net = client.networks.get(name)
        net.delete()
        return {"message": f"Network '{name}' deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
