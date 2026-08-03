import asyncio

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import registration, chat, sessions, hospital
from app.config import settings
from app.services.session_manager import SessionManager
from app.services.summary_service import SummaryService


# Background task: expire stale sessions every 60 seconds
async def session_expiry_task():
    """Runs in background. Expires sessions idle for 30+ minutes."""
    session_mgr = SessionManager()
    summary_svc = SummaryService()
    while True:
        await asyncio.sleep(60)
        expired_ids = session_mgr.expire_stale_sessions()
        # Generate partial summaries for expired sessions
        for sid in expired_ids:
            session = session_mgr.get(sid)
            if session and session.messages:
                try:
                    summary_svc.generate(session)
                except Exception:
                    pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background tasks on app startup."""
    task = asyncio.create_task(session_expiry_task())
    yield
    task.cancel()


app = FastAPI(
    title="Pre-Consult AI",
    description="Medical intake backend — registers patients, conducts AI intake, sends summary to hospital",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(registration.router, prefix="/api/v1", tags=["registration"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(sessions.router, prefix="/api/v1", tags=["sessions"])
app.include_router(hospital.router, prefix="/api/v1", tags=["hospital"])


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "0.2.0", "env": settings.app_env}
