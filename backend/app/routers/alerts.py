from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from boto3.dynamodb.conditions import Key, Attr
from app.db.dynamodb import Tables, scan_all, query_gsi
from app.models.alert import Alert, AlertAcknowledge
from app.models.common import RiskSeverity
from datetime import datetime

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[Alert])
async def list_alerts(
    severity: Optional[RiskSeverity] = Query(None),
    phc_id: Optional[str] = Query(None),
    acknowledged: Optional[bool] = Query(None),
    limit: int = Query(50, le=200),
):
    """Live alert feed with filters."""
    if phc_id:
        items = query_gsi(
            "resilia-alerts", "PHC-Alert-Index",
            Key("phc_id").eq(phc_id),
        )
    elif severity:
        items = query_gsi(
            "resilia-alerts", "Severity-Index",
            Key("severity").eq(severity.value),
        )
    else:
        items = scan_all("resilia-alerts")

    if acknowledged is not None:
        items = [i for i in items if i.get("acknowledged", False) == acknowledged]

    # Sort newest first
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return items[:limit]


@router.get("/unacknowledged/count")
async def unacked_count():
    """Count of unacknowledged alerts (for notification badge)."""
    items = scan_all("resilia-alerts", Attr("acknowledged").eq(False))
    by_sev = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for i in items:
        sev = i.get("severity", "LOW")
        by_sev[sev] = by_sev.get(sev, 0) + 1
    return {"total": len(items), "by_severity": by_sev}


@router.get("/{alert_id}", response_model=Alert)
async def get_alert(alert_id: str):
    """Fetch a single alert by ID."""
    resp = Tables.alerts().scan(
        FilterExpression=Attr("alert_id").eq(alert_id),
        Limit=1,
    )
    items = resp.get("Items", [])
    if not items:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return items[0]


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, body: AlertAcknowledge):
    """Acknowledge an alert."""
    # Find the alert's sort key (created_at)
    resp = Tables.alerts().scan(
        FilterExpression=Attr("alert_id").eq(alert_id)
    )
    items = resp.get("Items", [])
    if not items:
        raise HTTPException(status_code=404, detail="Alert not found")

    item = items[0]
    Tables.alerts().update_item(
        Key={"alert_id": alert_id, "created_at": item["created_at"]},
        UpdateExpression="SET acknowledged = :a, acknowledged_by = :ab, acknowledged_at = :aa",
        ExpressionAttributeValues={
            ":a": True,
            ":ab": body.acknowledged_by,
            ":aa": datetime.utcnow().isoformat(),
        },
    )
    return {"status": "acknowledged", "alert_id": alert_id}
