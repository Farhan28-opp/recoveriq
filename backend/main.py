import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import Base, engine
from backend.routes.health import router as health_router
from backend.routes.predict import router as predict_router
from backend.routes.recovery import router as recovery_router
from backend.routes.import_api import router as import_router
from backend.routes.transactions import router as transactions_router

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database tables exist (e.g. the new RecoveryWorkflow table)
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(
    title="RecoverIQ",
    description="AI-powered revenue recovery platform",
    version="0.5.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(predict_router)
app.include_router(recovery_router)
app.include_router(import_router)
app.include_router(transactions_router)
