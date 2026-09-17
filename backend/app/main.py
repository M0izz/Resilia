from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.config import settings
from app.db.dynamodb import create_tables
from app.routers import (
    health, phcs, inventory, patients, beds, staff,
    alerts, shipments, interventions,
)
from app.routers import (
    forecasts, sentinel, events as events_router, optimization, crisis,
    audit, agentic_loop, evaluation, demo,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create tables, start event bus, start sentinel agent."""
    logger.info("RESILIA API starting up — ensuring DynamoDB tables exist…")
    try:
        create_tables()
        logger.info("DynamoDB tables ready.")
    except Exception as exc:
        logger.warning("Could not create tables (may already exist): %s", exc)

    # ── Sprint 2: Start event bus then sentinel agent ──
    try:
        from app.events.event_bus import event_bus
        event_bus.start()
        logger.info("Event bus started.")
    except Exception as exc:
        logger.warning("Event bus failed to start: %s", exc)

    try:
        from app.agents.sentinel_agent import sentinel_agent
        sentinel_agent.start()
        logger.info("Sentinel Agent started.")
    except Exception as exc:
        logger.warning("Sentinel Agent failed to start: %s", exc)

    # ── Sprint 3: Start resource agent ──
    try:
        from app.agents.resource_agent import resource_agent
        resource_agent.start()
        logger.info("Resource Agent started.")
    except Exception as exc:
        logger.warning("Resource Agent failed to start: %s", exc)

    yield

    # ── Shutdown ──
    logger.info("RESILIA API shutting down…")
    try:
        from app.agents.sentinel_agent import sentinel_agent
        sentinel_agent.stop()
    except Exception:
        pass
    try:
        from app.events.event_bus import event_bus
        event_bus.stop()
    except Exception:
        pass
    logger.info("RESILIA API shut down cleanly.")


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=(
        "RESILIA — Federated AI Platform for Healthcare Supply-Chain Resilience. "
        "Monitors PHC networks, predicts resource failures, and coordinates responses."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers — Sprint 1 ───────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(phcs.router)
app.include_router(inventory.router)
app.include_router(patients.router)
app.include_router(beds.router)
app.include_router(staff.router)
app.include_router(alerts.router)
app.include_router(shipments.router)
app.include_router(interventions.router)

# ─── Routers — Sprint 2 ───────────────────────────────────────────────────
app.include_router(forecasts.router)
app.include_router(sentinel.router)
app.include_router(events_router.router)

# ─── Routers — Sprint 3 ───────────────────────────────────────────────────
app.include_router(optimization.router)

# ─── Routers — Sprint 4 ───────────────────────────────────────────────────
app.include_router(crisis.router)

# ─── Routers — Sprint 5 & Final Phase ─────────────────────────────────────
app.include_router(audit.router)
app.include_router(agentic_loop.router)
app.include_router(evaluation.router)
app.include_router(demo.router)


@app.get("/")
async def root():
    return {
        "service": "RESILIA API",
        "version": settings.api_version,
        "sprint":  "5 — National Command Center + AWS Integration + Productionization",
        "docs":    "/docs",
        "health":  "/health",
        "endpoints": [
            "/forecasts", "/sentinel", "/events", "/optimization",
            "/crisis/parse-scenario", "/crisis/simulate", "/crisis/network-graph", "/crisis/federated/train",
            "/audit/records", "/audit/verify-integrity", "/agentic-loop/run", "/agentic-loop/status",
            "/evaluation/benchmarks",
            "/demo/run-canonical-scenario", "/demo/canonical-scenario-status",
        ],
    }
