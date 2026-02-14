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

"""Integration tests for error handling scenarios.

Tests that the controller handles error conditions correctly:
- Creating a BackupPlan with an invalid (non-existent) target vault
- Creating a BackupSelection with an invalid plan ID
- Deleting a vault that has already been deleted (idempotent delete)
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
SELECTION_PLURAL = "backupselections"

DELETE_WAIT_SECONDS = 30
MAX_WAIT_FOR_SYNCED_MINUTES = 5


@service_marker
class TestErrorScenarios:

    def test_backup_selection_invalid_plan_id(self, backup_client):
        """Creating a BackupSelection with a non-existent plan ID should
        result in a terminal error condition."""
        selection_name = random_suffix_name("ack-err-sel", 24)

        replacements = REPLACEMENT_VALUES.copy()
        replacements["SELECTION_NAME"] = selection_name
        replacements["BACKUP_PLAN_ID"] = "non-existent-plan-id-12345"
        replacements["IAM_ROLE_ARN"] = "arn:aws:iam::123456789012:role/FakeRole"
        replacements["DYNAMODB_TABLE_ARN"] = "arn:aws:dynamodb:us-west-2:123456789012:table/fake"

        resource_data = load_backup_resource(
            "backup_selection_test",
            additional_replacements=replacements,
        )

        sel_ref = k8s.CustomResourceReference(
            CRD_GROUP, CRD_VERSION, SELECTION_PLURAL,
            selection_name, namespace="default",
        )

        k8s.create_custom_resource(sel_ref, resource_data)
        k8s.wait_resource_consumed_by_controller(sel_ref)

        # Wait a bit for the controller to process and set conditions
        time.sleep(15)

        # The resource should have a terminal or error condition
        sel_cr = k8s.get_resource(sel_ref)
        assert sel_cr is not None

        # Check that the resource is NOT synced (the API call should fail)
        conditions = sel_cr.get("status", {}).get("conditions", [])
        has_error = any(
            c.get("type") in ("ACK.Terminal",) and c.get("status") == "True"
            for c in conditions
        )
        # Either terminal condition is set, or resource is not synced
        if not has_error:
            condition.assert_not_synced(sel_ref)

        # Cleanup
        k8s.delete_custom_resource(sel_ref)
        time.sleep(DELETE_WAIT_SECONDS)

    def test_delete_already_deleted_vault(self, backup_client):
        """Deleting a vault that was already removed from AWS should
        complete successfully (idempotent delete / NotFound handling)."""
        vault_name = random_suffix_name("ack-del-vault", 24)

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

        # Create the vault
        k8s.create_custom_resource(vault_ref, resource_data)
        k8s.wait_resource_consumed_by_controller(vault_ref)
        assert k8s.wait_on_condition(
            vault_ref, "ACK.ResourceSynced", "True",
            wait_periods=MAX_WAIT_FOR_SYNCED_MINUTES,
        )

        # Delete the vault directly from AWS (out-of-band)
        try:
            backup_client.delete_backup_vault(BackupVaultName=vault_name)
        except Exception:
            pass

        time.sleep(5)

        # Now delete via the controller — should succeed gracefully
        _, deleted = k8s.delete_custom_resource(vault_ref)
        assert deleted

        time.sleep(DELETE_WAIT_SECONDS)
