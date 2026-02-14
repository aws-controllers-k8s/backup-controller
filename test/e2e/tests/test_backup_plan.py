# Copyright Amazon.com Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may
# not use this file except in compliance with the License. A copy of the
# License is located at
#
#	 http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is distributed
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.

"""Integration tests for the AWS Backup BackupPlan resource.

Tests the full CRUD lifecycle of BackupPlan custom resources:
- Create a vault (dependency), then create a plan referencing it
- Read the plan and verify status fields (planID, versionID)
- Update the plan rules and verify a new versionID is generated
- Delete the plan and verify cleanup
"""

import logging
import time
import pytest

from acktest.k8s import resource as k8s
from acktest.resources import random_suffix_name
from e2e import service_marker, CRD_GROUP, CRD_VERSION, load_backup_resource
from e2e.replacement_values import REPLACEMENT_VALUES
from e2e import condition

VAULT_PLURAL = "backupvaults"
PLAN_PLURAL = "backupplans"

MODIFY_WAIT_SECONDS = 10
DELETE_WAIT_SECONDS = 30
MAX_WAIT_FOR_SYNCED_MINUTES = 10


@pytest.fixture(scope="module")
def backup_vault_for_plan(backup_client):
    """Create a BackupVault that the BackupPlan tests can reference."""
    vault_name = random_suffix_name("ack-plan-vault", 24)

    replacements = REPLACEMENT_VALUES.copy()
    replacements["VAULT_NAME"] = vault_name

    resource_data = load_backup_resource(
        "backup_vault_test",
        additional_replacements=replacements,
    )

    vault_ref = k8s.CustomResourceReference(
        CRD_GROUP, CRD_VERSION, VAULT_PLURAL,
        vault_name, namespace="default",
    )

    k8s.create_custom_resource(vault_ref, resource_data)
    k8s.wait_resource_consumed_by_controller(vault_ref)
    assert k8s.wait_on_condition(
        vault_ref, "ACK.ResourceSynced", "True",
        wait_periods=MAX_WAIT_FOR_SYNCED_MINUTES,
    )

    yield vault_name, vault_ref

    # Teardown: delete the vault
    k8s.delete_custom_resource(vault_ref)
    time.sleep(DELETE_WAIT_SECONDS)


@service_marker
@pytest.mark.canary
class TestBackupPlan:

    def get_plan(self, backup_client, plan_id: str) -> dict:
        """Get a backup plan from AWS. Returns None if not found."""
        try:
            return backup_client.get_backup_plan(BackupPlanId=plan_id)
        except backup_client.exceptions.ResourceNotFoundException:
            return None
        except Exception as e:
            logging.debug(e)
            return None

    def test_crud_backup_plan(self, backup_client, backup_vault_for_plan):
        vault_name, _ = backup_vault_for_plan
        plan_name = random_suffix_name("ack-plan", 24)

        replacements = REPLACEMENT_VALUES.copy()
        replacements["PLAN_NAME"] = plan_name
        replacements["TARGET_VAULT_NAME"] = vault_name

        resource_data = load_backup_resource(
            "backup_plan_test",
            additional_replacements=replacements,
        )

        plan_ref = k8s.CustomResourceReference(
            CRD_GROUP, CRD_VERSION, PLAN_PLURAL,
            plan_name, namespace="default",
        )

        # --- CREATE ---
        k8s.create_custom_resource(plan_ref, resource_data)
        plan_cr = k8s.wait_resource_consumed_by_controller(plan_ref)

        assert plan_cr is not None
        assert k8s.get_resource_exists(plan_ref)

        assert k8s.wait_on_condition(
            plan_ref, "ACK.ResourceSynced", "True",
            wait_periods=MAX_WAIT_FOR_SYNCED_MINUTES,
        )

        # Refresh and verify status
        plan_cr = k8s.get_resource(plan_ref)
        assert "status" in plan_cr
        assert "backupPlanID" in plan_cr["status"]
        assert "versionID" in plan_cr["status"]
        assert "ackResourceMetadata" in plan_cr["status"]
        assert "arn" in plan_cr["status"]["ackResourceMetadata"]

        plan_id = plan_cr["status"]["backupPlanID"]
        original_version = plan_cr["status"]["versionID"]
        assert plan_id is not None
        assert original_version is not None

        # Verify in AWS
        aws_plan = self.get_plan(backup_client, plan_id)
        assert aws_plan is not None
        assert aws_plan["BackupPlan"]["BackupPlanName"] == plan_name
        assert len(aws_plan["BackupPlan"]["Rules"]) == 1
        assert aws_plan["BackupPlan"]["Rules"][0]["RuleName"] == "daily-backup-rule"

        # --- UPDATE ---
        updates = {
            "spec": {
                "backupPlan": {
                    "backupPlanName": plan_name,
                    "rules": [
                        {
                            "ruleName": "daily-backup-rule",
                            "targetBackupVaultName": vault_name,
                            "scheduleExpression": "cron(0 6 * * ? *)",
                            "startWindowMinutes": 120,
                            "completionWindowMinutes": 240,
                            "lifecycle": {
                                "deleteAfterDays": 90,
                            },
                        }
                    ],
                }
            }
        }

        k8s.patch_custom_resource(plan_ref, updates)
        time.sleep(MODIFY_WAIT_SECONDS)

        assert k8s.wait_on_condition(
            plan_ref, "ACK.ResourceSynced", "True",
            wait_periods=MAX_WAIT_FOR_SYNCED_MINUTES,
        )

        # Verify new version was created
        plan_cr = k8s.get_resource(plan_ref)
        new_version = plan_cr["status"]["versionID"]
        assert new_version is not None
        assert new_version != original_version

        # Verify updated values in AWS
        aws_plan = self.get_plan(backup_client, plan_id)
        assert aws_plan is not None
        rule = aws_plan["BackupPlan"]["Rules"][0]
        assert rule["ScheduleExpression"] == "cron(0 6 * * ? *)"
        assert rule["StartWindowMinutes"] == 120
        assert rule["CompletionWindowMinutes"] == 240
        assert rule["Lifecycle"]["DeleteAfterDays"] == 90

        # --- DELETE ---
        _, deleted = k8s.delete_custom_resource(plan_ref)
        assert deleted

        time.sleep(DELETE_WAIT_SECONDS)

        aws_plan = self.get_plan(backup_client, plan_id)
        assert aws_plan is None
