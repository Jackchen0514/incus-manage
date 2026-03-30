from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.core.limiter import limiter
from app.core.users import init_users
from app.routers import auth, instances, images, networks, storage, profiles, snapshots, system, proxy

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## Incus / LXD Management API

A RESTful API for managing Incus/LXD containers and virtual machines.

### Features
- **Instances** — create, start, stop, restart, delete containers and VMs
- **Images** — list, download, delete images
- **Networks** — manage bridge and overlay networks
- **Storage** — manage storage pools and volumes
- **Profiles** — manage instance profiles
- **Snapshots** — create, restore, delete snapshots
- **System** — view host resources and server info

### Authentication
All endpoints require a Bearer JWT token. Get one at `/api/v1/auth/token`.

Default credentials: `admin` / `admin123` (change via `ADMIN_PASSWORD` env var)

### Rate Limits
Limits are applied **per user** (authenticated) or **per IP** (unauthenticated).
Exceeding a limit returns HTTP **429 Too Many Requests**.

| Endpoint group | Default limit |
|----------------|--------------|
| Login | 10 / minute |
| Instance exec | 20 / minute |
| Write ops (create/delete/start/stop) | 30 / minute |
| All other endpoints | 60 / minute |
""",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Rate limiting ────────────────────────────────────────────────────────────
def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    retry_after = 60  # default fallback
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

# ── CORS ─────────────────────────────────────────────────────────────────────
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


@app.get("/", include_in_schema=False)
async def root():
    return {"service": settings.APP_NAME, "version": settings.APP_VERSION, "docs": "/docs"}


@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok"}


# Register all routers
app.include_router(auth.router)
app.include_router(instances.router)
app.include_router(images.router)
app.include_router(networks.router)
app.include_router(storage.router)
app.include_router(profiles.router)
app.include_router(snapshots.router)
app.include_router(system.router)
app.include_router(proxy.router)
