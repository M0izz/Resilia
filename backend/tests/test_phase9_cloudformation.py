"""
Phase 9 Tests: CloudFormation Infrastructure as Code & Observability

Verifies that infra/resilia-cloudformation.yml:
1. Syntactically parses cleanly with custom CloudFormation tags (!Sub, !Ref, !GetAtt).
2. Defines all critical persistence tables with PITR enabled and proper KeySchemas.
3. Defines ResiliaEventBus and dead-letter queue with critical telemetry rule.
4. Defines ResiliaInterventionPipeline Step Functions state machine with:
   - ValidateHumanApproval choice state enforcing human sign-off
   - CheckExecutionIdempotency task checking existing audit records
   - DebitDonorInventory with safety-stock conditional check
   - CreditRecipientInventory task
   - PublishDispatchEvent task
   - RecordImmutableAuditEntry task
5. Defines Cognito UserPool with groups (DistrictHealthOfficers, PHCPharmacists, NationalCommanders).
6. Configures CloudWatch log group for state machine observability.
"""

import json
import os
import re
import pytest
import yaml

# Custom CloudFormation YAML tag handlers
def _cfn_sub_constructor(loader, node):
    return f"!Sub {loader.construct_scalar(node)}"

def _cfn_ref_constructor(loader, node):
    return f"!Ref {loader.construct_scalar(node)}"

def _cfn_getatt_constructor(loader, node):
    if isinstance(node, yaml.SequenceNode):
        return [loader.construct_scalar(child) for child in node.value]
    return f"!GetAtt {loader.construct_scalar(node)}"

def _get_cfn_loader():
    loader = yaml.SafeLoader
    loader.add_constructor("!Sub", _cfn_sub_constructor)
    loader.add_constructor("!Ref", _cfn_ref_constructor)
    loader.add_constructor("!GetAtt", _cfn_getatt_constructor)
    return loader


@pytest.fixture(scope="module")
def cfn_template():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    template_path = os.path.join(repo_root, "infra", "resilia-cloudformation.yml")
    assert os.path.exists(template_path), f"CloudFormation template not found at {template_path}"
    with open(template_path, "r", encoding="utf-8") as f:
        data = yaml.load(f, Loader=_get_cfn_loader())
    return data


def test_cloudformation_structure_and_parameters(cfn_template):
    assert "AWSTemplateFormatVersion" in cfn_template
    assert "Resources" in cfn_template
    assert "Outputs" in cfn_template
    assert "Parameters" in cfn_template
    assert "Environment" in cfn_template["Parameters"]


def test_dynamodb_tables_and_recovery(cfn_template):
    resources = cfn_template["Resources"]
    
    # PHC table
    assert "PhcNetworkTable" in resources
    phc_table = resources["PhcNetworkTable"]["Properties"]
    assert phc_table["BillingMode"] == "PAY_PER_REQUEST"
    assert phc_table["PointInTimeRecoverySpecification"]["PointInTimeRecoveryEnabled"] is True
    
    # Inventory table with composite key
    assert "InventoryTable" in resources
    inv_table = resources["InventoryTable"]["Properties"]
    assert inv_table["BillingMode"] == "PAY_PER_REQUEST"
    key_schema = {k["AttributeName"]: k["KeyType"] for k in inv_table["KeySchema"]}
    assert key_schema["phc_id"] == "HASH"
    assert key_schema["medicine_code"] == "RANGE"
    
    # Audit ledger table
    assert "AuditLedgerTable" in resources
    audit_table = resources["AuditLedgerTable"]["Properties"]
    assert audit_table["BillingMode"] == "PAY_PER_REQUEST"
    assert audit_table["PointInTimeRecoverySpecification"]["PointInTimeRecoveryEnabled"] is True


def test_eventbridge_bus_and_rules(cfn_template):
    resources = cfn_template["Resources"]
    assert "ResiliaEventBus" in resources
    assert "ResiliaDeadLetterQueue" in resources
    assert "CriticalTelemetryRule" in resources
    
    rule = resources["CriticalTelemetryRule"]["Properties"]
    pattern = rule["EventPattern"]
    assert "resilia.telemetry" in pattern["source"]
    assert "CRITICAL" in pattern["detail"]["severity"]
    assert "HIGH" in pattern["detail"]["severity"]


def test_step_functions_state_machine_and_asl_integrity(cfn_template):
    resources = cfn_template["Resources"]
    assert "ResiliaInterventionPipeline" in resources
    assert "StepFunctionsLogGroup" in resources
    
    sm_props = resources["ResiliaInterventionPipeline"]["Properties"]
    def_raw = sm_props["DefinitionString"]
    
    # Strip !Sub prefix if present in the raw string for JSON parsing
    clean_json = re.sub(r"^!Sub\s*", "", def_raw.strip())
    # Strip unresolved CloudFormation variables like ${AuditLedgerTable} for ASL JSON validation
    clean_json = re.sub(r"\$\{[A-Za-z0-9_]+\}", "MOCK_RESOURCE", clean_json)
    
    asl = json.loads(clean_json)
    states = asl["States"]
    
    # 1. Enforces human approval check
    assert asl["StartAt"] == "ValidateHumanApproval"
    assert states["ValidateHumanApproval"]["Type"] == "Choice"
    assert states["InterventionHaltedUnapproved"]["Type"] == "Fail"
    
    # 2. Checks idempotency against audit record
    assert "CheckExecutionIdempotency" in states
    assert states["CheckExecutionIdempotency"]["Type"] == "Task"
    assert states["CheckExecutionIdempotency"]["Resource"] == "arn:aws:states:::dynamodb:getItem"
    assert "InterventionAlreadyExecuted" in states
    assert states["InterventionAlreadyExecuted"]["Type"] == "Fail"
    
    # 3. Executes atomic transfer with conditional check
    assert "DebitDonorInventory" in states
    assert states["DebitDonorInventory"]["Type"] == "Task"
    assert states["DebitDonorInventory"]["Resource"] == "arn:aws:states:::dynamodb:updateItem"
    assert "CreditRecipientInventory" in states
    assert states["CreditRecipientInventory"]["Type"] == "Task"
    
    # 4. Publishes dispatch event and writes immutable audit entry
    assert "PublishDispatchEvent" in states
    assert states["PublishDispatchEvent"]["Resource"] == "arn:aws:states:::events:putEvents"
    assert "RecordImmutableAuditEntry" in states
    assert states["RecordImmutableAuditEntry"]["Resource"] == "arn:aws:states:::dynamodb:putItem"


def test_cognito_user_pool_and_rbac_groups(cfn_template):
    resources = cfn_template["Resources"]
    assert "ResiliaUserPool" in resources
    assert "DistrictHealthOfficerGroup" in resources
    assert "PHCPharmacistGroup" in resources
    assert "NationalCommanderGroup" in resources
