import os
import secrets
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings, _gen_token
from app.core.limiter import limiter
from app.core.users import init_users
from app.routers import auth, instances, images, networks, storage, profiles, snapshots, system, proxy


# ── Resolve URL prefix ────────────────────────────────────────────────────────
# If API_PREFIX is not set, generate one, save it to .env, and use it.
_prefix = settings.API_PREFIX
if not _prefix:
    _prefix = _gen_token()
    # Reload settings won't happen at runtime, so use the generated value directly

PREFIX = f"/{_prefix}"   # e.g. /xK8mP2qL9rT5vNqW


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=f"""
## Incus / LXD Management API

All endpoints are mounted under the secret prefix: `{PREFIX}/api/v1/`

### Authentication
Get a token at `{PREFIX}/api/v1/auth/token` (username/password form).

### Rate Limits
| Endpoint group | Limit |
|----------------|-------|
| Login | 10 / minute |
| Instance exec | 20 / minute |
| Write ops | 30 / minute |
| Read ops | 60 / minute |
""",
    docs_url=f"{PREFIX}/docs",
    redoc_url=f"{PREFIX}/redoc",
    openapi_url=f"{PREFIX}/openapi.json",
)

# ── Rate limiting ─────────────────────────────────────────────────────────────
def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    retry_after = 60
    try:
        retry_after = exc.limit.limit.get_expiry()
    except Exception:
        pass
    return JSONResponse(
        status_code=429,
        content={"error": "Too Many Requests", "detail": str(exc.detail)},
        headers={"Retry-After": str(retry_after)},
    )

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
if settings.RATE_LIMIT_ENABLED:
    app.add_middleware(SlowAPIMiddleware)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    init_users()
    print(f"\n  Secret prefix : {PREFIX}")
    print(f"  Docs          : http://{settings.HOST}:{settings.PORT}{PREFIX}/docs\n")


@app.get("/health", tags=["System"], include_in_schema=False)
async def health():
    return {"status": "ok"}


# ── Routers (all mounted under secret PREFIX) ─────────────────────────────────
def _r(router, old_prefix: str):
    """Re-mount a router by replacing its /api/v1 prefix with PREFIX/api/v1."""
    new_prefix = router.prefix.replace("/api/v1", f"{PREFIX}/api/v1", 1)
    router.prefix = new_prefix
    return router

app.include_router(_r(auth.router,      "/api/v1/auth"))
app.include_router(_r(instances.router, "/api/v1/instances"))
app.include_router(_r(images.router,    "/api/v1/images"))
app.include_router(_r(networks.router,  "/api/v1/networks"))
app.include_router(_r(storage.router,   "/api/v1/storage"))
app.include_router(_r(profiles.router,  "/api/v1/profiles"))
app.include_router(_r(snapshots.router, "/api/v1/instances"))
app.include_router(_r(system.router,    "/api/v1/system"))
app.include_router(_r(proxy.router,     "/api/v1/instances"))
