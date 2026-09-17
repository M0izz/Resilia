from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from boto3.dynamodb.conditions import Key
from app.db.dynamodb import Tables
from app.models.inventory import InventoryItem, InventoryUpdate, InventorySnapshot
from app.services import risk_engine
from datetime import datetime

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/{phc_id}", response_model=list[InventoryItem])
async def get_phc_inventory(phc_id: str):
    """All medicines in stock at a PHC, with risk scores."""
    resp = Tables.inventory().query(
        KeyConditionExpression=Key("phc_id").eq(phc_id)
    )
    items = resp.get("Items", [])
    if not items:
        raise HTTPException(status_code=404, detail=f"No inventory for PHC {phc_id}")

    # Enrich with computed days_of_stock and risk
    for item in items:
        qty = float(item.get("quantity", 0))
        cons = float(item.get("daily_consumption", 1))
        dos = risk_engine.days_of_stock(qty, cons)
        item["days_of_stock"] = dos

        med = risk_engine.MedicineRiskInput(
            medicine_code=item["medicine_code"],
            medicine_name=item.get("medicine_name", ""),
            quantity=qty,
            daily_consumption=cons,
            criticality=item.get("criticality", "MEDIUM"),
        )
        result = risk_engine.score_medicine(med)
        item["risk_score"] = result.risk_score
        item["risk_severity"] = result.risk_severity.value

    return items


@router.get("/{phc_id}/snapshot", response_model=InventorySnapshot)
async def inventory_snapshot(phc_id: str):
    """Summary: worst days of stock, items below reorder, expiring soon."""
    resp = Tables.inventory().query(
        KeyConditionExpression=Key("phc_id").eq(phc_id)
    )
    items = resp.get("Items", [])
    if not items:
        raise HTTPException(status_code=404, detail=f"No inventory for PHC {phc_id}")

    critical_count = 0
    below_reorder = 0
    expiring_30d = 0
    worst_dos = 999.0
    worst_med = ""

    today = datetime.utcnow().date()

    for item in items:
        qty = float(item.get("quantity", 0))
        cons = float(item.get("daily_consumption", 1))
        dos = risk_engine.days_of_stock(qty, cons)

        if item.get("criticality") in ("CRITICAL", "HIGH") and dos < 14:
            critical_count += 1

        if qty < float(item.get("reorder_level", 0)):
            below_reorder += 1

        try:
            from datetime import date
            exp = date.fromisoformat(item.get("expiry_date", "2099-01-01"))
            days_to_exp = (exp - today).days
            if 0 < days_to_exp <= 30:
                expiring_30d += 1
        except Exception:
            pass

        if dos < worst_dos:
            worst_dos = dos
            worst_med = item.get("medicine_name", "")

    return InventorySnapshot(
        phc_id=phc_id,
        total_medicines=len(items),
        critical_items=critical_count,
        items_below_reorder=below_reorder,
        items_expiring_30d=expiring_30d,
        worst_days_of_stock=worst_dos if worst_dos < 999 else 0.0,
        worst_medicine=worst_med,
    )


@router.get("/{phc_id}/{medicine_code}", response_model=InventoryItem)
async def get_medicine(phc_id: str, medicine_code: str):
    """Single medicine stock at a PHC."""
    resp = Tables.inventory().get_item(
        Key={"phc_id": phc_id, "medicine_code": medicine_code}
    )
    item = resp.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Medicine not found")
    return item


@router.patch("/{phc_id}/{medicine_code}")
async def update_stock(phc_id: str, medicine_code: str, update: InventoryUpdate):
    """Update quantity for a medicine (manual stock update)."""
    resp = Tables.inventory().get_item(
        Key={"phc_id": phc_id, "medicine_code": medicine_code}
    )
    if not resp.get("Item"):
        raise HTTPException(status_code=404, detail="Medicine not found")

    Tables.inventory().update_item(
        Key={"phc_id": phc_id, "medicine_code": medicine_code},
        UpdateExpression="SET quantity = :q, last_updated = :lu",
        ExpressionAttributeValues={
            ":q": update.quantity,
            ":lu": datetime.utcnow().isoformat(),
        },
    )
    return {"status": "updated", "phc_id": phc_id, "medicine_code": medicine_code, "new_quantity": update.quantity}


@router.get("/shortages/district")
async def district_shortages(
    state_code: str = Query(...),
    district_code: str = Query(...),
    severity: str = Query("HIGH"),
):
    """
    All medicine shortages across a district.
    Used by the Resource Agent to find donors and recipients.
    """
    from app.db.dynamodb import scan_all, query_gsi
    from boto3.dynamodb.conditions import Attr

    # Get PHC IDs in district
    phcs = query_gsi(
        "resilia-phcs", "State-Index",
        Key("state_code").eq(state_code) & Key("district_code").eq(district_code),
    )
    phc_ids = {p["phc_id"] for p in phcs}

    # Scan inventory for shortages
    all_inv = scan_all("resilia-inventory")
    shortages = []
    for item in all_inv:
        if item.get("phc_id") not in phc_ids:
            continue
        dos = risk_engine.days_of_stock(
            float(item.get("quantity", 0)),
            float(item.get("daily_consumption", 1))
        )
        if dos < 14 and item.get("criticality") in ("CRITICAL", "HIGH"):
            shortages.append({**item, "days_of_stock": dos})

    return sorted(shortages, key=lambda x: x["days_of_stock"])
