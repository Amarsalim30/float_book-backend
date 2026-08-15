import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.routers import auth, dashboard, transactions, people, onboarding, mpesa, tracked_accounts, ledger
from app.services import mpesa_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _prune_unused_mpesa_messages()
    yield


def _prune_unused_mpesa_messages() -> None:
    db = SessionLocal()
    try:
        deleted = mpesa_service.prune_unused_messages(db)
        db.commit()
        if deleted:
            logger.info("Pruned %d unused M-Pesa message(s) on startup", deleted)
    except Exception:
        db.rollback()
        logger.warning("Startup M-Pesa message prune failed; skipping", exc_info=True)
    finally:
        db.close()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_PREFIX}/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(onboarding.router, prefix=settings.API_PREFIX)
app.include_router(dashboard.router, prefix=settings.API_PREFIX)
app.include_router(transactions.router, prefix=settings.API_PREFIX)
app.include_router(ledger.router, prefix=settings.API_PREFIX)
app.include_router(people.router, prefix=settings.API_PREFIX)
app.include_router(mpesa.router, prefix=settings.API_PREFIX)
app.include_router(tracked_accounts.router, prefix=settings.API_PREFIX)


@app.get("/health")
def health_check():
    return {"status": "healthy"}
