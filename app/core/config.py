from pydantic_settings import BaseSettings
from typing import Optional
import os
import secrets


def _gen_token() -> str:
    """Generate a random URL prefix token and persist it to .env."""
    token = secrets.token_urlsafe(24)
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    env_path = os.path.normpath(env_path)
    # Append only if not already set
    if os.path.exists(env_path):
        content = open(env_path).read()
        if "API_PREFIX=" in content:
            return token  # will be overridden by env file value anyway
    with open(env_path, "a") as f:
        f.write(f"\nAPI_PREFIX={token}\n")
    return token


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Incus Manager API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 5000
    # URL secret prefix — all routes are mounted under /<API_PREFIX>/api/v1/
    # Auto-generated on first start; set API_PREFIX in .env to pin a value.
    API_PREFIX: str = ""

    # Security
    SECRET_KEY: str = "change-this-secret-key-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # LXD/Incus socket path
    LXD_SOCKET: str = "/var/snap/lxd/common/lxd/unix.socket"

    # Admin user (created on first start)
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"

    # Rate limiting (slowapi / limits syntax)
    # Format: "count/period"  e.g. "60/minute", "1000/hour", "10/second"
    RATE_LIMIT_DEFAULT: str = "60/minute"     # general API calls per IP
    RATE_LIMIT_LOGIN: str = "10/minute"       # login endpoint (brute-force protection)
    RATE_LIMIT_EXEC: str = "20/minute"        # exec inside instance
    RATE_LIMIT_WRITE: str = "30/minute"       # create/delete/start/stop operations
    RATE_LIMIT_ENABLED: bool = True

    model_config = {"env_file": ".env"}


settings = Settings()
