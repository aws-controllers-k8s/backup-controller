# Copyright Amazon.com Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may
# not use this file except in compliance with the License. A copy of the
# License is located at
#
# 	 http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is distributed
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.

"""Integration tests for the AWS Backup BackupVault resource.
"""

import pytest
import time
import logging

from acktest.resources import random_suffix_name
from acktest.k8s import resource as k8s
from acktest.k8s import condition
from e2e import service_marker, CRD_GROUP, CRD_VERSION, load_backup_resource
from e2e.replacement_values import REPLACEMENT_VALUES

RESOURCE_PLURAL = "backupvaults"

CREATE_WAIT_AFTER_SECONDS = 10
UPDATE_WAIT_AFTER_SECONDS = 10
DELETE_WAIT_AFTER_SECONDS = 10


@service_marker
@pytest.mark.canary
class TestBackupVault:
    def get_backup_vault(self, backup_client, vault_name: str) -> dict:
        """Get a backup vault by name."""
        try:
            resp = backup_client.describe_backup_vault(
                BackupVaultName=vault_name
            )
            return resp
        except backup_client.exceptions.ResourceNotFoundException:
            return None
        except Exception as e:
            logging.debug(e)
            return None

    def vault_exists(self, backup_client, vault_name: str) -> bool:
        """Check if a backup vault exists."""
        return self.get_backup_vault(backup_client, vault_name) is not None

    def test_create_delete(self, backup_client):
        """Test basic create and delete operations for BackupVault."""
        resource_name = random_suffix_name("ack-test-vault", 24)

        replacements = REPLACEMENT_VALUES.copy()
        replacements["VAULT_NAME"] = resource_name

        # Load BackupVault CR
        resource_data = load_backup_resource(
            "backup_vault",
            additional_replacements=replacements,
        )
        logging.debug(resource_data)

        # Create k8s resource
        ref = k8s.CustomResourceReference(
            CRD_GROUP, CRD_VERSION, RESOURCE_PLURAL,
            resource_name, namespace="default",
        )
        k8s.create_custom_resource(ref, resource_data)
        cr = k8s.wait_resource_consumed_by_controller(ref)

        assert cr is not None
        assert k8s.get_resource_exists(ref)

        time.sleep(CREATE_WAIT_AFTER_SECONDS)
        assert k8s.wait_on_condition(ref, condition.CONDITION_TYPE_RESOURCE_SYNCED, "True", wait_periods=5)

        # Check vault exists in AWS
        assert self.vault_exists(backup_client, resource_name)

        vault = self.get_backup_vault(backup_client, resource_name)
        assert vault is not None
        assert vault["BackupVaultName"] == resource_name

        # Delete k8s resource
        _, deleted = k8s.delete_custom_resource(ref)
        assert deleted

        time.sleep(DELETE_WAIT_AFTER_SECONDS)

        # Check vault deleted from AWS
        assert not self.vault_exists(backup_client, resource_name)

    def test_create_with_encryption_key(self, backup_client):
        """Test creating a BackupVault with a custom encryption key."""
        resource_name = random_suffix_name("ack-test-vault-enc", 24)

        replacements = REPLACEMENT_VALUES.copy()
        replacements["VAULT_NAME"] = resource_name
        # Note: For this test to work, you'd need a valid KMS key ARN
        # This test is a placeholder for when encryption key testing is needed

        # Load BackupVault CR
        resource_data = load_backup_resource(
            "backup_vault",
            additional_replacements=replacements,
        )
        logging.debug(resource_data)

        # Create k8s resource
        ref = k8s.CustomResourceReference(
            CRD_GROUP, CRD_VERSION, RESOURCE_PLURAL,
            resource_name, namespace="default",
        )
        k8s.create_custom_resource(ref, resource_data)
        cr = k8s.wait_resource_consumed_by_controller(ref)

        assert cr is not None
        assert k8s.get_resource_exists(ref)

        time.sleep(CREATE_WAIT_AFTER_SECONDS)
        assert k8s.wait_on_condition(ref, condition.CONDITION_TYPE_RESOURCE_SYNCED, "True", wait_periods=5)

        # Check vault exists in AWS
        assert self.vault_exists(backup_client, resource_name)

        # Verify status fields are populated
        cr = k8s.get_resource(ref)
        assert 'status' in cr
        assert 'ackResourceMetadata' in cr['status']
        assert 'arn' in cr['status']['ackResourceMetadata']

        # Delete k8s resource
        _, deleted = k8s.delete_custom_resource(ref)
        assert deleted

        time.sleep(DELETE_WAIT_AFTER_SECONDS)

        # Check vault deleted from AWS
        assert not self.vault_exists(backup_client, resource_name)
