from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Incus Manager API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

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
