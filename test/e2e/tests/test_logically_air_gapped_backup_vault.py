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

"""Integration tests for the LogicallyAirGappedBackupVault resource.
"""

import pytest
import time
import logging

from acktest.resources import random_suffix_name
from acktest.k8s import resource as k8s
from acktest import tags
from e2e import service_marker, CRD_GROUP, CRD_VERSION, load_backup_resource
from e2e.replacement_values import REPLACEMENT_VALUES

RESOURCE_PLURAL = "logicallyairgappedbackupvaults"

# Vault creation moves through VaultState CREATING before reaching AVAILABLE,
# which the synced condition waits on, so allow more periods than a standard
# vault needs.
CREATE_WAIT_AFTER_SECONDS = 10
CREATE_WAIT_PERIODS = 20
UPDATE_WAIT_AFTER_SECONDS = 10
DELETE_WAIT_AFTER_SECONDS = 10

MIN_RETENTION_DAYS = 7
MAX_RETENTION_DAYS = 30

UPDATED_TAGS = {
    "ManagedBy": "ACK",
    "environment": "testing",
}


@pytest.fixture(scope="module")
def simple_air_gapped_vault(backup_client):
    resource_name = random_suffix_name("ack-test-lag-vault", 32)

    replacements = REPLACEMENT_VALUES.copy()
    replacements["VAULT_NAME"] = resource_name

    resource_data = load_backup_resource(
        "logically_air_gapped_backup_vault",
        additional_replacements=replacements,
    )
    logging.debug(resource_data)

    ref = k8s.CustomResourceReference(
        CRD_GROUP, CRD_VERSION, RESOURCE_PLURAL,
        resource_name, namespace="default",
    )
    k8s.create_custom_resource(ref, resource_data)
    cr = k8s.wait_resource_consumed_by_controller(ref)

    assert cr is not None
    assert k8s.get_resource_exists(ref)

    yield (ref, cr)

    # Teardown
    try:
        _, deleted = k8s.delete_custom_resource(ref, 3, 10)
        assert deleted
    except:
        pass


@service_marker
class TestLogicallyAirGappedBackupVault:
    def test_crud(self, backup_client, simple_air_gapped_vault):
        (ref, cr) = simple_air_gapped_vault

        time.sleep(CREATE_WAIT_AFTER_SECONDS)
        assert k8s.wait_on_condition(
            ref, "ACK.ResourceSynced", "True", wait_periods=CREATE_WAIT_PERIODS
        )

        vault_name = cr["spec"]["name"]

        # Verify in AWS, including that this really is an air-gapped vault and
        # not a standard one. The controller reads both types through the same
        # DescribeBackupVault API.
        response = backup_client.describe_backup_vault(BackupVaultName=vault_name)
        assert response["BackupVaultName"] == vault_name
        assert response["VaultType"] == "LOGICALLY_AIR_GAPPED_BACKUP_VAULT"
        assert response["MinRetentionDays"] == MIN_RETENTION_DAYS
        assert response["MaxRetentionDays"] == MAX_RETENTION_DAYS

        # Verify the status fields sourced from DescribeBackupVault. VaultState
        # is only populated for this vault type, which is why the synced
        # condition can key on it.
        cr = k8s.get_resource(ref)
        assert cr["status"].get("vaultState") == "AVAILABLE"
        assert cr["status"].get("vaultType") == "LOGICALLY_AIR_GAPPED_BACKUP_VAULT"
        assert cr["status"].get("creationDate") is not None

        # The vault ARN has to land in ACKResourceMetadata rather than a plain
        # status field. Tag reads and writes are guarded on it, so they go
        # quietly nowhere when it is unset.
        assert cr["status"]["ackResourceMetadata"]["arn"] == response["BackupVaultArn"]

        # Verify the retention window round-trips into the spec, so it does not
        # read back as a permanent delta on every resync.
        assert cr["spec"]["minRetentionDays"] == MIN_RETENTION_DAYS
        assert cr["spec"]["maxRetentionDays"] == MAX_RETENTION_DAYS

        # Tags are the only mutable field on this resource: there is no update
        # API for the vault itself.
        k8s.patch_custom_resource(ref, {"spec": {"tags": UPDATED_TAGS}})
        time.sleep(UPDATE_WAIT_AFTER_SECONDS)
        assert k8s.wait_on_condition(ref, "ACK.ResourceSynced", "True", wait_periods=5)

        tags_response = backup_client.list_tags(
            ResourceArn=response["BackupVaultArn"]
        )
        aws_tags = tags_response.get("Tags", {})
        tags.assert_ack_system_tags(tags=aws_tags)
        tags.assert_equal_without_ack_tags(expected=UPDATED_TAGS, actual=aws_tags)

        # Delete and verify the vault is gone from AWS. An empty vault deletes
        # cleanly; DeleteBackupVault refuses a vault that holds recovery points.
        _, deleted = k8s.delete_custom_resource(ref, 3, 10)
        assert deleted
        time.sleep(DELETE_WAIT_AFTER_SECONDS)

        try:
            backup_client.describe_backup_vault(BackupVaultName=vault_name)
            assert False, (
                f"LogicallyAirGappedBackupVault {vault_name} still exists in AWS "
                "after deletion"
            )
        except backup_client.exceptions.ResourceNotFoundException:
            pass
        except backup_client.exceptions.AccessDeniedException:
            # DescribeBackupVault answers AccessDenied for a vault that no
            # longer exists, which is why the controller maps 404 to it.
            pass
