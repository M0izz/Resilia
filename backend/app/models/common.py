"""Shared enums and base types used across all RESILIA models."""
from enum import Enum


class RiskSeverity(str, Enum):
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    # Backward compatibility aliases for existing seeded records
    LOW = "LOW"
    MEDIUM = "MEDIUM"


class RiskCategory(str, Enum):
    MEDICINE_STOCKOUT = "MEDICINE_STOCKOUT"
    BED_OVERLOAD = "BED_OVERLOAD"
    PATIENT_SURGE = "PATIENT_SURGE"
    STAFF_SHORTAGE = "STAFF_SHORTAGE"
    SUPPLIER_DISRUPTION = "SUPPLIER_DISRUPTION"
    COMBINED_CASCADING = "COMBINED_CASCADING"


class ZoneType(str, Enum):
    URBAN = "Urban"
    SEMI_URBAN = "Semi-urban"
    RURAL = "Rural"
    TRIBAL = "Tribal"


class MedicineCriticality(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertType(str, Enum):
    STOCKOUT_RISK = "STOCKOUT_RISK"
    SUPPLIER_DELAY = "SUPPLIER_DELAY"
    BED_OVERFLOW = "BED_OVERFLOW"
    STAFF_SHORTAGE = "STAFF_SHORTAGE"
    PATIENT_SURGE = "PATIENT_SURGE"
    EXPIRY_WARNING = "EXPIRY_WARNING"
    DATA_GAP = "DATA_GAP"
    COMPOUND = "COMPOUND"


class ShipmentStatus(str, Enum):
    PENDING = "PENDING"
    IN_TRANSIT = "IN_TRANSIT"
    DELAYED = "DELAYED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class InterventionStatus(str, Enum):
    PROPOSED = "PROPOSED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
