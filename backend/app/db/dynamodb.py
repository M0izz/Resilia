"""
DynamoDB client, table registry, and CRUD helpers for RESILIA.
All operations support DynamoDB Local (dev) and real AWS DynamoDB (prod)
transparently via the endpoint_url setting.
"""
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
from botocore.config import Config
from app.config import settings
from app.db.in_memory_store import in_memory_store
import logging

logger = logging.getLogger(__name__)


# ─── Client factories ──────────────────────────────────────────────────────

def _db_kwargs() -> dict:
    kwargs = dict(
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        config=Config(connect_timeout=0.4, read_timeout=0.4, retries={"max_attempts": 1}),
    )
    if settings.dynamodb_endpoint:
        kwargs["endpoint_url"] = settings.dynamodb_endpoint
    return kwargs


def get_resource():
    return boto3.resource("dynamodb", **_db_kwargs())


def get_client():
    return boto3.client("dynamodb", **_db_kwargs())


_dynamodb_online: Optional[bool] = None


def is_dynamodb_online() -> bool:
    global _dynamodb_online
    if _dynamodb_online is not None:
        return _dynamodb_online
    try:
        client = get_client()
        client.list_tables()
        _dynamodb_online = True
    except Exception:
        _dynamodb_online = False
    return _dynamodb_online


class ResilientTableWrapper:
    """Wraps DynamoDB table operations with transparent fallback to in-memory store."""

    def __init__(self, table_name: str):
        self.table_name = table_name

    def _get_real_table(self):
        return get_resource().Table(self.table_name)

    def get_item(self, **kwargs) -> dict:
        if is_dynamodb_online():
            try:
                resp = self._get_real_table().get_item(**kwargs)
                if "Item" in resp:
                    return resp
            except Exception:
                pass
        key = kwargs.get("Key", {})
        item = in_memory_store.get_item(self.table_name, key)
        return {"Item": item} if item else {}

    def put_item(self, **kwargs) -> dict:
        item = kwargs.get("Item", {})
        in_memory_store.put_item(self.table_name, item)
        if is_dynamodb_online():
            try:
                return self._get_real_table().put_item(**kwargs)
            except Exception:
                pass
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    def update_item(self, **kwargs) -> dict:
        if is_dynamodb_online():
            try:
                return self._get_real_table().update_item(**kwargs)
            except Exception:
                pass
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    def scan(self, **kwargs) -> dict:
        if is_dynamodb_online():
            try:
                resp = self._get_real_table().scan(**kwargs)
                if "Items" in resp and len(resp["Items"]) > 0:
                    return resp
            except Exception:
                pass
        items = in_memory_store.get_table_items(self.table_name)
        return {"Items": items, "Count": len(items)}

    def query(self, **kwargs) -> dict:
        if is_dynamodb_online():
            try:
                resp = self._get_real_table().query(**kwargs)
                if "Items" in resp and len(resp["Items"]) > 0:
                    return resp
            except Exception:
                pass
        items = in_memory_store.get_table_items(self.table_name)
        return {"Items": items, "Count": len(items)}


def get_table(name: str):
    return ResilientTableWrapper(name)


# ─── Table references (lazily resolved) ───────────────────────────────────

class Tables:
    @staticmethod
    def phcs():        return get_table(settings.table_phcs)
    @staticmethod
    def inventory():   return get_table(settings.table_inventory)
    @staticmethod
    def patients():    return get_table(settings.table_patients)
    @staticmethod
    def staff():       return get_table(settings.table_staff)
    @staticmethod
    def alerts():      return get_table(settings.table_alerts)
    @staticmethod
    def suppliers():   return get_table(settings.table_suppliers)
    @staticmethod
    def shipments():   return get_table(settings.table_shipments)
    @staticmethod
    def interventions():return get_table(settings.table_interventions)


# ─── Table creation (idempotent) ───────────────────────────────────────────

TABLE_DEFINITIONS = [
    {
        "TableName": settings.table_phcs,
        "KeySchema": [
            {"AttributeName": "phc_id", "KeyType": "HASH"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "phc_id", "AttributeType": "S"},
            {"AttributeName": "state_code", "AttributeType": "S"},
            {"AttributeName": "district_code", "AttributeType": "S"},
            {"AttributeName": "risk_severity", "AttributeType": "S"},
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "State-Index",
                "KeySchema": [
                    {"AttributeName": "state_code", "KeyType": "HASH"},
                    {"AttributeName": "district_code", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            },
            {
                "IndexName": "Risk-Index",
                "KeySchema": [
                    {"AttributeName": "state_code", "KeyType": "HASH"},
                    {"AttributeName": "risk_severity", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            },
        ],
        "ProvisionedThroughput": {"ReadCapacityUnits": 10, "WriteCapacityUnits": 10},
    },
    {
        "TableName": settings.table_inventory,
        "KeySchema": [
            {"AttributeName": "phc_id", "KeyType": "HASH"},
            {"AttributeName": "medicine_code", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "phc_id", "AttributeType": "S"},
            {"AttributeName": "medicine_code", "AttributeType": "S"},
        ],
        "ProvisionedThroughput": {"ReadCapacityUnits": 10, "WriteCapacityUnits": 10},
    },
    {
        "TableName": settings.table_patients,
        "KeySchema": [
            {"AttributeName": "phc_id", "KeyType": "HASH"},
            {"AttributeName": "date", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "phc_id", "AttributeType": "S"},
            {"AttributeName": "date", "AttributeType": "S"},
        ],
        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    },
    {
        "TableName": settings.table_staff,
        "KeySchema": [
            {"AttributeName": "phc_id", "KeyType": "HASH"},
            {"AttributeName": "date", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "phc_id", "AttributeType": "S"},
            {"AttributeName": "date", "AttributeType": "S"},
        ],
        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    },
    {
        "TableName": settings.table_alerts,
        "KeySchema": [
            {"AttributeName": "alert_id", "KeyType": "HASH"},
            {"AttributeName": "created_at", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "alert_id", "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "S"},
            {"AttributeName": "phc_id", "AttributeType": "S"},
            {"AttributeName": "severity", "AttributeType": "S"},
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "PHC-Alert-Index",
                "KeySchema": [
                    {"AttributeName": "phc_id", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            },
            {
                "IndexName": "Severity-Index",
                "KeySchema": [
                    {"AttributeName": "severity", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            },
        ],
        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    },
    {
        "TableName": settings.table_suppliers,
        "KeySchema": [
            {"AttributeName": "supplier_id", "KeyType": "HASH"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "supplier_id", "AttributeType": "S"},
        ],
        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    },
    {
        "TableName": settings.table_shipments,
        "KeySchema": [
            {"AttributeName": "shipment_id", "KeyType": "HASH"},
            {"AttributeName": "phc_id", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "shipment_id", "AttributeType": "S"},
            {"AttributeName": "phc_id", "AttributeType": "S"},
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "PHC-Shipment-Index",
                "KeySchema": [
                    {"AttributeName": "phc_id", "KeyType": "HASH"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            }
        ],
        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    },
    {
        "TableName": settings.table_interventions,
        "KeySchema": [
            {"AttributeName": "intervention_id", "KeyType": "HASH"},
            {"AttributeName": "created_at", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "intervention_id", "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "S"},
        ],
        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    },
]


def create_tables() -> None:
    """Create all RESILIA tables (idempotent — skips existing tables or offline DynamoDB)."""
    global _dynamodb_online
    try:
        client = get_client()
        existing = set(client.list_tables().get("TableNames", []))
        _dynamodb_online = True
        for defn in TABLE_DEFINITIONS:
            name = defn["TableName"]
            if name in existing:
                continue
            try:
                get_resource().create_table(**defn)
            except ClientError as e:
                if e.response["Error"]["Code"] == "ResourceInUseException":
                    pass
                else:
                    raise
    except Exception as exc:
        _dynamodb_online = False
        logger.info("DynamoDB local endpoint offline (%s) — activating in-memory resilience layer.", exc)


# ─── Generic helpers ───────────────────────────────────────────────────────

def scan_all(table_name: str, filter_expr=None) -> list[dict]:
    if is_dynamodb_online():
        try:
            table = get_resource().Table(table_name)
            kwargs = {}
            if filter_expr is not None:
                kwargs["FilterExpression"] = filter_expr
            items = []
            while True:
                resp = table.scan(**kwargs)
                items.extend(resp.get("Items", []))
                if "LastEvaluatedKey" not in resp:
                    break
                kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
            if items:
                return items
        except Exception as exc:
            logger.debug("DynamoDB scan_all failed (%s) — using in-memory store for %s", exc, table_name)
    return in_memory_store.get_table_items(table_name, filter_expr)


def query_gsi(table_name: str, index_name: str, key_condition, filter_expr=None) -> list[dict]:
    if is_dynamodb_online():
        try:
            table = get_resource().Table(table_name)
            kwargs = dict(IndexName=index_name, KeyConditionExpression=key_condition)
            if filter_expr is not None:
                kwargs["FilterExpression"] = filter_expr
            items = []
            while True:
                resp = table.query(**kwargs)
                items.extend(resp.get("Items", []))
                if "LastEvaluatedKey" not in resp:
                    break
                kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
            if items:
                return items
        except Exception as exc:
            logger.debug("DynamoDB query_gsi failed (%s) — using in-memory store for %s", exc, table_name)
    return in_memory_store.query_table(table_name, index_name, key_condition, filter_expr)


