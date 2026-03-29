"""
Simple in-memory user store. Replace with a database for production.
"""
from typing import Optional
from app.core.security import get_password_hash
from app.core.config import settings

# Structure: {username: {username, hashed_password, is_admin, is_active}}
users_db: dict = {}


def init_users():
    """Create default admin user if no users exist."""
    if not users_db:
        users_db[settings.ADMIN_USERNAME] = {
            "username": settings.ADMIN_USERNAME,
            "hashed_password": get_password_hash(settings.ADMIN_PASSWORD),
            "is_admin": True,
            "is_active": True,
        }


def get_user(username: str) -> "Optional[dict]":
    return users_db.get(username)


def create_user(username: str, password: str, is_admin: bool = False) -> dict:
    user = {
        "username": username,
        "hashed_password": get_password_hash(password),
        "is_admin": is_admin,
        "is_active": True,
    }
    users_db[username] = user
    return user


def list_users() -> list:
    return [
        {"username": u["username"], "is_admin": u["is_admin"], "is_active": u["is_active"]}
        for u in users_db.values()
    ]


def delete_user(username: str) -> bool:
    if username in users_db:
        del users_db[username]
        return True
    return False
