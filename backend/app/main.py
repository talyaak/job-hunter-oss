import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, health, insights, leads, onboarding, preferences, profile, rejects, search, sync
from app.config import settings
from app.db.session import Base, SessionLocal, engine
from app.envfile import ensure_access_token
from app.ingestion.sync_guard import recover_orphaned_sync_runs
from app.scheduler.cron import start_scheduler
from app.security import AccessGateMiddleware
from app.sync_hub import hub

logging.basicConfig(level=logging.INFO, format="%(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    hub.bind_loop(asyncio.get_running_loop())
    Base.metadata.create_all(bind=engine)
    ensure_access_token()  # first run: generate + persist so the tunnel is never open by default
    if settings.ingestion_enabled:
        with SessionLocal() as db:
            n = recover_orphaned_sync_runs(db)
            if n:
                logging.info("[Sync] Recovered %s orphaned running ingestion run(s)", n)
        start_scheduler()
    yield


app = FastAPI(title="Job Hunter API", lifespan=lifespan)

# Order matters: the gate is added first (inner), CORS last (outer) so 401s still carry CORS headers.
app.add_middleware(AccessGateMiddleware)
origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(leads.router)
app.include_router(rejects.router)
app.include_router(sync.router)
app.include_router(profile.router)
app.include_router(search.router)
app.include_router(preferences.router)
app.include_router(onboarding.router)
app.include_router(insights.router)
