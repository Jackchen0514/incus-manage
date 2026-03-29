"""
LXD/Incus client wrapper using pylxd.
Auto-detects the socket path if the configured one does not exist.
"""
from __future__ import annotations
from typing import Optional
import os
import pylxd
from fastapi import HTTPException
from app.core.config import settings


# Known socket paths in priority order
_SOCKET_CANDIDATES = [
    settings.LXD_SOCKET,
    "/var/lib/incus/unix.socket",       # Incus (standard)
    "/run/incus/unix.socket",            # Incus (some distros)
    "/var/snap/lxd/common/lxd/unix.socket",  # LXD (snap)
    "/var/lib/lxd/unix.socket",          # LXD (non-snap)
]

_client: Optional[pylxd.Client] = None


def _find_socket() -> str:
    for path in _SOCKET_CANDIDATES:
        if os.path.exists(path):
            return path
    raise HTTPException(
        status_code=503,
        detail=(
            "Cannot connect to Incus/LXD: no socket found. "
            f"Tried: {', '.join(_SOCKET_CANDIDATES)}. "
            "Set LXD_SOCKET in .env to the correct path."
        ),
    )


def get_client() -> pylxd.Client:
    global _client
    if _client is None:
        socket_path = _find_socket()
        try:
            _client = pylxd.Client(
                endpoint=f"http+unix://{socket_path.replace('/', '%2F')}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail=f"Cannot connect to Incus/LXD socket '{socket_path}': {e}",
            )
    return _client


def reset_client():
    """Force reconnect (useful after config change)."""
    global _client
    _client = None
