from fastapi import APIRouter
from datetime import datetime
from app.db.dynamodb import get_client
from app.config import settings
import boto3

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check():
    """Liveness check."""
    return {
        "status": "ok",
        "service": "RESILIA API",
        "version": settings.api_version,
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.environment,
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
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
