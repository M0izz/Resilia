from fastapi import APIRouter, HTTPException, Query
from boto3.dynamodb.conditions import Key, Attr
from app.db.dynamodb import Tables, scan_all
from app.models.intervention import Intervention, InterventionApproval, InterventionRejection
from app.models.common import InterventionStatus
from datetime import datetime
import uuid

router = APIRouter(prefix="/interventions", tags=["interventions"])


@router.get("", response_model=list[Intervention])
async def list_interventions(status: str = Query(None)):
    """All intervention plans, optionally filtered by status."""
    items = scan_all("resilia-interventions")
    if status:
        items = [i for i in items if i.get("status") == status]
    return sorted(items, key=lambda x: x.get("created_at", ""), reverse=True)


@router.get("/pending")
async def pending_interventions():
    """Interventions awaiting human approval (for the notification badge)."""
    items = scan_all(
        "resilia-interventions",
        Attr("status").eq(InterventionStatus.AWAITING_APPROVAL.value),
    )
    return {"count": len(items), "items": items}


@router.get("/{intervention_id}", response_model=Intervention)
async def get_intervention(intervention_id: str):
    resp = Tables.interventions().scan(
        FilterExpression=Attr("intervention_id").eq(intervention_id)
    )
    items = resp.get("Items", [])
    if not items:
        raise HTTPException(status_code=404, detail="Intervention not found")
    return items[0]


@router.post("/{intervention_id}/approve")
async def approve_intervention(intervention_id: str, body: InterventionApproval):
    """Human approves the intervention plan."""
    resp = Tables.interventions().scan(
        FilterExpression=Attr("intervention_id").eq(intervention_id)
    )
    items = resp.get("Items", [])
    if not items:
        raise HTTPException(status_code=404, detail="Intervention not found")

    item = items[0]
    now = datetime.utcnow().isoformat()
    Tables.interventions().update_item(
        Key={"intervention_id": intervention_id, "created_at": item["created_at"]},
        UpdateExpression="SET #s = :s, approved_by = :ab, approved_at = :aa",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": InterventionStatus.APPROVED.value,
            ":ab": body.approved_by,
            ":aa": now,
        },
    )
    return {"status": "approved", "intervention_id": intervention_id, "approved_at": now}


@router.post("/{intervention_id}/reject")
async def reject_intervention(intervention_id: str, body: InterventionRejection):
    """Human rejects the intervention plan with a reason."""
    resp = Tables.interventions().scan(
        FilterExpression=Attr("intervention_id").eq(intervention_id)
    )
    items = resp.get("Items", [])
    if not items:
        raise HTTPException(status_code=404, detail="Intervention not found")

    item = items[0]
    Tables.interventions().update_item(
        Key={"intervention_id": intervention_id, "created_at": item["created_at"]},
        UpdateExpression="SET #s = :s, rejection_reason = :r",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": InterventionStatus.REJECTED.value,
            ":r": body.reason,
        },
    )
    return {"status": "rejected", "intervention_id": intervention_id}
