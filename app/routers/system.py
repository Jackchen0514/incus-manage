from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.security import get_current_active_user
from app.core.limiter import limiter
from app.core.config import settings
from app.services.lxd_client import get_client

router = APIRouter(prefix="/api/v1/system", tags=["System"])


@router.get("/info", summary="Get LXD server info and resources")
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def server_info(request: Request, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        host = client.host_info
        resources = client.resources
        return {
            "api_version": host.get("api_version"),
            "server_version": host.get("environment", {}).get("server_version"),
            "kernel_version": host.get("environment", {}).get("kernel_version"),
            "os_name": host.get("environment", {}).get("os_name"),
            "architectures": host.get("environment", {}).get("architectures"),
            "driver": host.get("environment", {}).get("driver"),
            "storage": host.get("environment", {}).get("storage"),
            "resources": {
                "cpu": resources.get("cpu", {}),
                "memory": resources.get("memory", {}),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resources", summary="Get host resource usage")
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def server_resources(request: Request, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        return client.resources
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
