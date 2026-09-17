from fastapi import APIRouter, HTTPException, Query
from boto3.dynamodb.conditions import Key
from app.db.dynamodb import Tables
from app.models.staff import DailyStaffRecord, StaffAttendanceSummary
from app.services.risk_engine import doctor_attendance_pct, nurse_attendance_pct
from datetime import datetime, date

router = APIRouter(prefix="/staff", tags=["staff"])


@router.get("/{phc_id}/today", response_model=StaffAttendanceSummary)
async def get_today_attendance(phc_id: str):
    """Today's staff attendance summary."""
    today = date.today().isoformat()
    resp = Tables.staff().get_item(Key={"phc_id": phc_id, "date": today})
    item = resp.get("Item")
    if not item:
        # Fall back to most recent record
        resp2 = Tables.staff().query(
            KeyConditionExpression=Key("phc_id").eq(phc_id),
            ScanIndexForward=False,
            Limit=1,
        )
        records = resp2.get("Items", [])
        if not records:
            raise HTTPException(status_code=404, detail="No staff records")
        item = records[0]

    dt = int(item.get("doctors_total", 0))
    dp = int(item.get("doctors_present", 0))
    nt = int(item.get("nurses_total", 0))
    np_ = int(item.get("nurses_present", 0))
    at = int(item.get("asha_total", 0))
    aa = int(item.get("asha_active", 0))

    doc_pct = doctor_attendance_pct(dp, dt)
    nur_pct = nurse_attendance_pct(np_, nt)
    asha_pct = nurse_attendance_pct(aa, at)

    shortage_types = []
    if dp < dt:
        shortage_types.append("doctors")
    if np_ < nt:
        shortage_types.append("nurses")

    return StaffAttendanceSummary(
        phc_id=phc_id,
        date=item.get("date", today),
        doctor_attendance_pct=doc_pct,
        nurse_attendance_pct=nur_pct,
        asha_active_pct=asha_pct,
        is_understaffed=bool(shortage_types),
        shortage_types=shortage_types,
    )


@router.get("/{phc_id}/history", response_model=list[DailyStaffRecord])
async def get_staff_history(phc_id: str, days: int = Query(7, ge=1, le=30)):
    """Staff attendance history for the last N days."""
    from datetime import timedelta
    cutoff = (datetime.utcnow() - timedelta(days=days)).date().isoformat()
    resp = Tables.staff().query(
        KeyConditionExpression=Key("phc_id").eq(phc_id) & Key("date").gte(cutoff),
        ScanIndexForward=False,
    )
    return resp.get("Items", [])
