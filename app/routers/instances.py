from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List, Dict

from app.core.security import get_current_active_user
from app.core.limiter import limiter
from app.core.config import settings
from app.services.lxd_client import get_client
from app.services.ssh_setup import generate_password, find_free_port, setup_ssh, add_ssh_proxy

router = APIRouter(prefix="/api/v1/instances", tags=["Instances"])


class InstanceCreate(BaseModel):
    name: str
    image: str = "ubuntu/22.04"
    image_server: Optional[str] = "https://images.linuxcontainers.org"
    instance_type: str = "container"  # "container" or "virtual-machine"
    profiles: List[str] = ["default"]
    config: Dict = {}
    devices: Dict = {}        # raw Incus devices, merged with bandwidth settings below
    auto_start: bool = True   # start the instance after creation
    setup_ssh: bool = False   # install openssh-server, set root password, add port forward
    # Bandwidth limits (Mbit/s, 0 = unlimited)
    bandwidth_ingress: int = 0
    bandwidth_egress: int = 0


class ExecCommand(BaseModel):
    command: List[str]
    environment: Dict = {}
    wait: bool = True


def _get_host_ip() -> str:
    """Return the host's primary public/private IP for SSH connection info."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def _wait_for_ip(inst, timeout: int = 30) -> Optional[str]:
    """Poll instance state until an IPv4 address appears or timeout."""
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            state = inst.state()
            network = state.network or {}
            for iface, data in network.items():
                if iface == "lo":
                    continue
                for addr in data.get("addresses", []):
                    if addr.get("family") == "inet":
                        return addr["address"]
        except Exception:
            pass
        time.sleep(1)
    return None


def _instance_to_dict(inst) -> dict:
    try:
        state = inst.state()
        network = state.network or {}
        addresses = {}
        for iface, data in network.items():
            ips = [a["address"] for a in data.get("addresses", []) if a.get("family") == "inet"]
            if ips:
                addresses[iface] = ips
    except Exception:
        state = None
        addresses = {}

    return {
        "name": inst.name,
        "status": inst.status,
        "type": inst.type,
        "profiles": inst.profiles,
        "config": dict(inst.config),
        "created_at": str(inst.created_at) if hasattr(inst, "created_at") else None,
        "addresses": addresses,
    }


@router.get("", summary="List all instances")
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def list_instances(request: Request, _=Depends(get_current_active_user)):
    client = get_client()
    instances = client.instances.all()
    return [_instance_to_dict(i) for i in instances]


@router.get("/{name}", summary="Get instance details")
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def get_instance(request: Request, name: str, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        inst = client.instances.get(name)
        return _instance_to_dict(inst)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Instance '{name}' not found")


@router.post("", status_code=201, summary="Create a new instance")
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def create_instance(request: Request, data: InstanceCreate, _=Depends(get_current_active_user)):
    import logging
    logger = logging.getLogger("instances")

    client = get_client()

    # Normalize image alias: "ubuntu:22.04" -> "ubuntu/22.04" for simplestreams
    image_alias = data.image.replace(":", "/")

    if data.image_server:
        source = {
            "type": "image",
            "mode": "pull",
            "server": data.image_server,
            "protocol": "simplestreams",
            "alias": image_alias,
        }
    else:
        source = {
            "type": "image",
            "alias": image_alias,
        }

    # Build devices dict: start from user-supplied, then apply bandwidth limits
    devices = dict(data.devices)
    if data.bandwidth_ingress or data.bandwidth_egress:
        eth0 = dict(devices.get("eth0", {"type": "nic", "nictype": "bridged", "parent": "incusbr0"}))
        if data.bandwidth_ingress:
            eth0["limits.ingress"] = f"{data.bandwidth_ingress}Mbit"
        if data.bandwidth_egress:
            eth0["limits.egress"] = f"{data.bandwidth_egress}Mbit"
        devices["eth0"] = eth0

    config = {
        "name": data.name,
        "source": source,
        "profiles": data.profiles,
        "config": data.config,
        "devices": devices,
        "type": data.instance_type,
    }

    logger.info("Creating instance: name=%s image=%s server=%s", data.name, image_alias, data.image_server)
    try:
        inst = client.instances.create(config, wait=True)

        ip = None
        ssh_info = None

        if data.auto_start:
            inst.start(wait=True)
            ip = _wait_for_ip(inst, timeout=30)

        if data.setup_ssh:
            if not ip:
                raise HTTPException(status_code=400, detail="Cannot setup SSH: instance has no IP (is it running?)")
            password = generate_password()
            host_port = find_free_port(client)
            setup_ssh(inst, password)
            add_ssh_proxy(inst, host_port, ip)
            ssh_info = {
                "host": _get_host_ip(),
                "port": host_port,
                "username": "root",
                "password": password,
            }
            logger.info("SSH ready: instance=%s port=%d", data.name, host_port)

        return {
            "message": f"Instance '{data.name}' created",
            "name": inst.name,
            "status": inst.status,
            "ip": ip,
            "ssh": ssh_info,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Instance creation failed: %s | config=%s", e, config)
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{name}", summary="Delete an instance")
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def delete_instance(request: Request, name: str, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        inst = client.instances.get(name)
        if inst.status == "Running":
            inst.stop(wait=True)
        inst.delete(wait=True)
        return {"message": f"Instance '{name}' deleted"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{name}/start", summary="Start an instance")
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def start_instance(request: Request, name: str, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        inst = client.instances.get(name)
        inst.start(wait=True)
        return {"message": f"Instance '{name}' started", "status": inst.status}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{name}/stop", summary="Stop an instance")
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def stop_instance(request: Request, name: str, force: bool = False, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        inst = client.instances.get(name)
        inst.stop(force=force, wait=True)
        return {"message": f"Instance '{name}' stopped", "status": inst.status}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{name}/restart", summary="Restart an instance")
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def restart_instance(request: Request, name: str, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        inst = client.instances.get(name)
        inst.restart(wait=True)
        return {"message": f"Instance '{name}' restarted", "status": inst.status}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{name}/freeze", summary="Freeze (pause) an instance")
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def freeze_instance(request: Request, name: str, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        inst = client.instances.get(name)
        inst.freeze(wait=True)
        return {"message": f"Instance '{name}' frozen"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{name}/unfreeze", summary="Unfreeze (resume) an instance")
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def unfreeze_instance(request: Request, name: str, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        inst = client.instances.get(name)
        inst.unfreeze(wait=True)
        return {"message": f"Instance '{name}' unfrozen"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{name}/exec", summary="Execute a command inside an instance")
@limiter.limit(settings.RATE_LIMIT_EXEC)
async def exec_command(request: Request, name: str, data: ExecCommand, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        inst = client.instances.get(name)
        result = inst.execute(data.command, environment=data.environment)
        return {
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{name}/state", summary="Get instance state (CPU, memory, network, disk)")
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def get_instance_state(request: Request, name: str, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        inst = client.instances.get(name)
        state = inst.state()
        return {
            "status": state.status,
            "cpu": state.cpu,
            "memory": state.memory,
            "network": state.network,
            "disk": state.disk,
            "pid": state.pid,
            "processes": state.processes,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{name}/setup-ssh", summary="Install SSH, set root password, add port forward")
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def setup_instance_ssh(request: Request, name: str, _=Depends(get_current_active_user)):
    import logging
    logger = logging.getLogger("instances")
    client = get_client()
    try:
        inst = client.instances.get(name)
        if inst.status != "Running":
            raise HTTPException(status_code=400, detail=f"Instance must be running (current: {inst.status})")

        ip = _wait_for_ip(inst, timeout=15)
        if not ip:
            raise HTTPException(status_code=504, detail="Could not determine instance IP")

        password = generate_password()
        host_port = find_free_port(client)
        setup_ssh(inst, password)
        add_ssh_proxy(inst, host_port, ip)

        logger.info("SSH setup done: instance=%s port=%d", name, host_port)
        return {
            "name": name,
            "ip": ip,
            "ssh": {
                "host": _get_host_ip(),
                "port": host_port,
                "username": "root",
                "password": password,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{name}/ip", summary="Get instance IPv4 address (waits up to 30s)")
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def get_instance_ip(request: Request, name: str, timeout: int = 30, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        inst = client.instances.get(name)
        if inst.status != "Running":
            raise HTTPException(status_code=400, detail=f"Instance '{name}' is not running (status: {inst.status})")
        ip = _wait_for_ip(inst, timeout=min(timeout, 60))
        if not ip:
            raise HTTPException(status_code=504, detail="IP address not assigned within timeout")
        return {"name": name, "ip": ip}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{name}/config", summary="Update instance configuration")
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def update_config(request: Request, name: str, config: dict, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        inst = client.instances.get(name)
        inst.config.update(config)
        inst.save(wait=True)
        return {"message": "Config updated", "config": dict(inst.config)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Bandwidth ─────────────────────────────────────────────────────────────────

class BandwidthUpdate(BaseModel):
    ingress: int = 0   # Mbit/s, 0 = unlimited
    egress: int = 0    # Mbit/s, 0 = unlimited


@router.get("/{name}/bandwidth", summary="Get current bandwidth limits for an instance")
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def get_bandwidth(request: Request, name: str, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        inst = client.instances.get(name)
        eth0 = inst.devices.get("eth0", {})
        return {
            "name": name,
            "ingress": eth0.get("limits.ingress", "unlimited"),
            "egress": eth0.get("limits.egress", "unlimited"),
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{name}/bandwidth", summary="Set bandwidth limits for an instance (0 = unlimited)")
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def set_bandwidth(request: Request, name: str, data: BandwidthUpdate, _=Depends(get_current_active_user)):
    client = get_client()
    try:
        inst = client.instances.get(name)
        eth0 = dict(inst.devices.get("eth0", {"type": "nic", "nictype": "bridged", "parent": "incusbr0"}))

        if data.ingress:
            eth0["limits.ingress"] = f"{data.ingress}Mbit"
        else:
            eth0.pop("limits.ingress", None)

        if data.egress:
            eth0["limits.egress"] = f"{data.egress}Mbit"
        else:
            eth0.pop("limits.egress", None)

        inst.devices["eth0"] = eth0
        inst.save(wait=True)

        return {
            "message": "Bandwidth limits updated",
            "name": name,
            "ingress": f"{data.ingress}Mbit" if data.ingress else "unlimited",
            "egress": f"{data.egress}Mbit" if data.egress else "unlimited",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
