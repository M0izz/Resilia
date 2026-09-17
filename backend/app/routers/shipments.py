from fastapi import APIRouter, HTTPException, Query
from boto3.dynamodb.conditions import Key, Attr
from app.db.dynamodb import Tables, scan_all, query_gsi
from app.models.shipment import Shipment

router = APIRouter(prefix="/shipments", tags=["shipments"])


@router.get("/{phc_id}", response_model=list[Shipment])
async def get_phc_shipments(phc_id: str):
    """All shipments (pending, in-transit, delayed) for a PHC."""
    items = query_gsi("resilia-shipments", "PHC-Shipment-Index", Key("phc_id").eq(phc_id))
    return sorted(items, key=lambda x: x.get("expected_delivery", ""), reverse=False)


@router.get("/delayed/all")
async def get_all_delayed(state_code: str = Query(None)):
    """All delayed shipments, optionally filtered by state."""
    items = scan_all("resilia-shipments", Attr("status").eq("DELAYED"))
    if state_code:
        phc_ids = {
            p["phc_id"] for p in scan_all("resilia-phcs", Attr("state_code").eq(state_code))
        }
        items = [i for i in items if i.get("phc_id") in phc_ids]
    return items


@router.patch("/{shipment_id}/status")
async def update_shipment_status(
    shipment_id: str,
    phc_id: str = Query(...),
    status: str = Query(...),
    delay_days: int = Query(0),
    delay_reason: str = Query(""),
):
    """Update shipment status (e.g., mark as DELIVERED or DELAYED)."""
    resp = Tables.shipments().get_item(Key={"shipment_id": shipment_id, "phc_id": phc_id})
    if not resp.get("Item"):
        raise HTTPException(status_code=404, detail="Shipment not found")

    from datetime import datetime
    Tables.shipments().update_item(
        Key={"shipment_id": shipment_id, "phc_id": phc_id},
        UpdateExpression="SET #s = :s, delay_days = :d, delay_reason = :r",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": status,
            ":d": delay_days,
            ":r": delay_reason,
        },
    )
    return {"status": "updated", "shipment_id": shipment_id, "new_status": status}
