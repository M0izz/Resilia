from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # DynamoDB
    dynamodb_endpoint: str = "http://localhost:8001"
    aws_region: str = "us-east-1"
    aws_access_key_id: str = "local"
    aws_secret_access_key: str = "local"

    # App
    environment: str = "local"
    api_title: str = "RESILIA — Healthcare Resilience Platform"
    api_version: str = "1.0.0"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8501"]

    # DynamoDB table names
    table_phcs: str = "resilia-phcs"
    table_inventory: str = "resilia-inventory"
    table_patients: str = "resilia-patients"
    table_staff: str = "resilia-staff"
    table_alerts: str = "resilia-alerts"
    table_suppliers: str = "resilia-suppliers"
    table_shipments: str = "resilia-shipments"
    table_interventions: str = "resilia-interventions"


settings = Settings()
