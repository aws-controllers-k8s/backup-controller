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

"""Integration tests for the AWS Backup BackupVault resource.

Tests the full CRUD lifecycle of BackupVault custom resources:
- Create a vault and verify it exists in AWS
- Read/describe the vault and verify status fields
- Delete the vault and verify cleanup
"""

import logging
import time
import pytest

from acktest.k8s import resource as k8s
from acktest.resources import random_suffix_name
from e2e import service_marker, CRD_GROUP, CRD_VERSION, load_backup_resource
from e2e.replacement_values import REPLACEMENT_VALUES
from e2e import condition

RESOURCE_PLURAL = "backupvaults"

CREATE_WAIT_SECONDS = 10
DELETE_WAIT_SECONDS = 30
MAX_WAIT_FOR_SYNCED_MINUTES = 10


@service_marker
@pytest.mark.canary
class TestBackupVault:

    def get_vault(self, backup_client, vault_name: str) -> dict:
        """Describe a backup vault in AWS. Returns None if not found."""
        try:
            return backup_client.describe_backup_vault(
                BackupVaultName=vault_name,
            )
        except backup_client.exceptions.ResourceNotFoundException:
            return None
        except Exception as e:
            logging.debug(e)
            return None

    def test_crud_backup_vault(self, backup_client):
        vault_name = random_suffix_name("ack-vault", 24)

        replacements = REPLACEMENT_VALUES.copy()
        replacements["VAULT_NAME"] = vault_name

        resource_data = load_backup_resource(
            "backup_vault_test",
            additional_replacements=replacements,
        )

        vault_ref = k8s.CustomResourceReference(
            CRD_GROUP, CRD_VERSION, RESOURCE_PLURAL,
            vault_name, namespace="default",
        )

        # --- CREATE ---
        k8s.create_custom_resource(vault_ref, resource_data)
        vault_cr = k8s.wait_resource_consumed_by_controller(vault_ref)

        assert vault_cr is not None
        assert k8s.get_resource_exists(vault_ref)

        # BackupVault creation is synchronous, so it should sync quickly
        assert k8s.wait_on_condition(
            vault_ref, "ACK.ResourceSynced", "True",
            wait_periods=MAX_WAIT_FOR_SYNCED_MINUTES,
        )

        # Refresh the CR and verify status fields
        vault_cr = k8s.get_resource(vault_ref)
        assert vault_cr is not None
        assert "status" in vault_cr
        assert "ackResourceMetadata" in vault_cr["status"]
        assert "arn" in vault_cr["status"]["ackResourceMetadata"]
        assert vault_name in vault_cr["status"]["ackResourceMetadata"]["arn"]

        # Verify the vault exists in AWS
        aws_vault = self.get_vault(backup_client, vault_name)
        assert aws_vault is not None
        assert aws_vault["BackupVaultName"] == vault_name
        assert aws_vault["NumberOfRecoveryPoints"] == 0

        # Verify status fields populated from describe
        assert "numberOfRecoveryPoints" in vault_cr["status"]
        assert vault_cr["status"]["numberOfRecoveryPoints"] == 0

        # --- DELETE ---
        _, deleted = k8s.delete_custom_resource(vault_ref)
        assert deleted

        time.sleep(DELETE_WAIT_SECONDS)

        # Verify vault is gone from AWS
        aws_vault = self.get_vault(backup_client, vault_name)
        assert aws_vault is None
