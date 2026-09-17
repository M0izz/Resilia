from pydantic import BaseModel
from typing import Optional
from app.models.common import ShipmentStatus


class ShipmentItem(BaseModel):
    medicine_code: str
    medicine_name: str
    quantity: float
    unit: str
    batch_number: str
    expiry_date: str


class Shipment(BaseModel):
    shipment_id: str
    phc_id: str
    supplier_id: str
    supplier_name: str

    status: ShipmentStatus
    ordered_at: str
    expected_delivery: str
    actual_delivery: Optional[str] = None

    delay_days: int = 0
    delay_reason: Optional[str] = None

    items: list[ShipmentItem]
    total_value_inr: Optional[float] = None
    notes: Optional[str] = None
