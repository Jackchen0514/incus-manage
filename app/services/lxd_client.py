"""
LXD/Incus client wrapper using pylxd.
Provides a singleton client connected to the local LXD socket.
"""
from __future__ import annotations
from typing import Optional
import pylxd
from app.core.config import settings


_client: Optional[pylxd.Client] = None


def get_client() -> pylxd.Client:
    global _client
    if _client is None:
        _client = pylxd.Client(endpoint=f"http+unix://{settings.LXD_SOCKET.replace('/', '%2F')}")
    return _client


def reset_client():
    """Force reconnect (useful after config change)."""
    global _client
    _client = None
