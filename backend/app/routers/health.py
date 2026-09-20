"""
Health check endpoints.

Phase 2 — Silent Fallback: the /health response now includes a `data_source`
field so the dashboard can display a prominent banner when the API is operating
on the synthetic in-memory dataset rather than live DynamoDB.
"""
from fastapi import APIRouter
from datetime import datetime
from app.db.dynamodb import get_client, get_data_source, is_dynamodb_online
from app.config import settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check():
    """
    Liveness check.

    Returns `data_source`:
    - `'LIVE'` — DynamoDB is reachable; data is live.
    - `'SYNTHETIC-IN-MEMORY'` — DynamoDB is offline; the API is serving the
      bundled 75-PHC synthetic demo dataset.  The dashboard will show a
      disclaimer banner.
    """
    online = is_dynamodb_online()
    return {
        "status": "ok",
        "service": "RESILIA API",
        "version": settings.api_version,
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.environment,
        "data_source": "LIVE" if online else "SYNTHETIC-IN-MEMORY",
        "dynamodb_online": online,
        "disclaimer": (
            None if online
            else (
                "DynamoDB Local is offline. The API is serving the bundled "
                "synthetic 75-PHC demo dataset. Data shown is NOT from a live "
                "deployment."
            )
        ),
    }


@router.get("/db")
async def db_check():
    """Check DynamoDB connectivity and list tables."""
    try:
        client = get_client()
        tables = client.list_tables()["TableNames"]
        return {
            "status": "ok",
            "dynamodb_endpoint": settings.dynamodb_endpoint,
            "tables_found": len(tables),
            "tables": tables,
            "data_source": "LIVE",
        }
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "data_source": "SYNTHETIC-IN-MEMORY",
            "disclaimer": (
                "DynamoDB Local is offline. The API is serving the bundled "
                "synthetic 75-PHC demo dataset."
            ),
        }
