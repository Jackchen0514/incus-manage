"""
Proxy device (port forwarding) management for Incus instances.

Underlying Incus primitive:
  incus config device add <instance> <device> type=proxy \
      listen=tcp:0.0.0.0:<host_port> connect=tcp:<instance_ip>:<instance_port>
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from app.core.security import get_current_active_user
from app.core.limiter import limiter
from app.core.config import settings
from app.services.lxd_client import get_client

router = APIRouter(prefix="/api/v1/instances", tags=["Proxy / Port Forwarding"])


class ProxyCreate(BaseModel):
    host_port: int                      # port to listen on the host (e.g. 8080)
    instance_port: int                  # port inside the container (e.g. 80)
    protocol: str = "tcp"               # tcp | udp
    device_name: Optional[str] = None   # auto-generated if omitted: "proxy-<host_port>"
    bind_address: str = "0.0.0.0"       # host bind address


def _get_proxy_devices(inst) -> list:
    return [
        {
            "device": name,
            "listen": cfg.get("listen"),
            "connect": cfg.get("connect"),
            "protocol": cfg.get("listen", "").split(":")[0] if cfg.get("listen") else "tcp",
        }
        for name, cfg in inst.devices.items()
        if cfg.get("type") == "proxy"
    ]


def _instance_ip(inst) -> Optional[str]:
    try:
        network = inst.state().network or {}
        for iface, data in network.items():
            if iface == "lo":
                continue
            for addr in data.get("addresses", []):
                if addr.get("family") == "inet":
                    return addr["address"]
    except Exception:
        pass
    return None


@router.get("/{name}/proxy", summary="List all proxy devices (port forwards) for an instance")
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def list_proxy(request: Request, name: str, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        inst = client.instances.get(name)
        return {"name": name, "proxies": _get_proxy_devices(inst)}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{name}/proxy", status_code=201, summary="Add a port forward to an instance")
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def add_proxy(request: Request, name: str, data: ProxyCreate, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        inst = client.instances.get(name)

        # Resolve instance IP
        ip = _instance_ip(inst)
        if not ip:
            raise HTTPException(
                status_code=400,
                detail="Instance has no IPv4 address — is it running?",
            )

        device_name = data.device_name or f"proxy-{data.protocol}-{data.host_port}"

        if device_name in inst.devices:
            raise HTTPException(
                status_code=409,
                detail=f"Device '{device_name}' already exists on instance '{name}'",
            )

        inst.devices[device_name] = {
            "type": "proxy",
            "listen": f"{data.protocol}:{data.bind_address}:{data.host_port}",
            "connect": f"{data.protocol}:{ip}:{data.instance_port}",
        }
        inst.save(wait=True)

        return {
            "message": f"Proxy '{device_name}' added",
            "device": device_name,
            "listen": f"{data.protocol}:{data.bind_address}:{data.host_port}",
            "connect": f"{data.protocol}:{ip}:{data.instance_port}",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{name}/proxy/{device_name}", summary="Remove a port forward from an instance")
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def delete_proxy(request: Request, name: str, device_name: str, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        inst = client.instances.get(name)

        if device_name not in inst.devices:
            raise HTTPException(status_code=404, detail=f"Device '{device_name}' not found")

        if inst.devices[device_name].get("type") != "proxy":
            raise HTTPException(status_code=400, detail=f"Device '{device_name}' is not a proxy device")

        del inst.devices[device_name]
        inst.save(wait=True)

        return {"message": f"Proxy '{device_name}' removed from instance '{name}'"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
