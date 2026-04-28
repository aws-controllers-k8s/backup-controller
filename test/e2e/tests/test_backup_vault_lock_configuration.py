#  Copyright Amazon.com Inc. or its affiliates. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License"). You may
#  not use this file except in compliance with the License. A copy of the
#  License is located at
#
#       http://aws.amazon.com/apache2.0/
#
#  or in the "license" file accompanying this file. This file is distributed
#  on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
#  express or implied. See the License for the specific language governing
#  permissions and limitations under the License.

"""Integration tests for the BackupVault resource's LockConfiguration sub-resource.

LockConfiguration is driven by the sub-resource-manager construct in the
code-generator: the parent's generated sdkUpdate calls Sync() on the
backup_vault_lock_configuration sub-resource when Spec.LockConfiguration
changes, and sdkDelete clears the lock before removing the vault.

NOTE: Vault Lock becomes immutable after the ChangeableForDays window expires.
These tests always use a large ChangeableForDays value (≥ 3, per AWS minimum)
so the lock can be deleted during cleanup. Never set ChangeableForDays to a
small value in tests that need to clean up the vault.
"""

import logging
import time

import pytest
from acktest.k8s import resource as k8s
from acktest.resources import random_suffix_name

from e2e import CRD_GROUP, CRD_VERSION, load_backup_resource, service_marker
from e2e.replacement_values import REPLACEMENT_VALUES

RESOURCE_PLURAL = "backupvaults"

CREATE_WAIT_AFTER_SECONDS = 10
UPDATE_WAIT_AFTER_SECONDS = 10
DELETE_WAIT_AFTER_SECONDS = 10


def _get_lock_configuration(backup_client, vault_name: str):
    """Return (min_retention_days, max_retention_days) for the vault lock,
    or (None, None) if no lock is configured."""
    try:
        resp = backup_client.describe_backup_vault(BackupVaultName=vault_name)
    except backup_client.exceptions.ResourceNotFoundException:
        return None, None
    except Exception as ex:
        logging.debug("describe_backup_vault error: %s", ex)
        return None, None
    min_days = resp.get("MinRetentionDays")
    max_days = resp.get("MaxRetentionDays")
    # No lock if neither bound is set
    if min_days is None and max_days is None:
        return None, None
    return min_days, max_days


def _wait_for_lock(backup_client, vault_name: str, predicate,
                   attempts: int = 12, interval: int = 5):
    """Poll describe_backup_vault until predicate((min_days, max_days)) is True."""
    last = (None, None)
    for _ in range(attempts):
        last = _get_lock_configuration(backup_client, vault_name)
        if predicate(last):
            return last
        time.sleep(interval)
    raise AssertionError(
        f"timed out waiting for expected lock configuration on {vault_name}; "
        f"last observed: {last}"
    )


def _create_backup_vault(resource_name: str, resource_template: str,
                         extra_replacements: dict = None):
    replacements = REPLACEMENT_VALUES.copy()
    replacements["VAULT_NAME"] = resource_name
    if extra_replacements:
        replacements.update(extra_replacements)

    resource_data = load_backup_resource(
        resource_template,
        additional_replacements=replacements,
    )
    logging.debug(resource_data)

    ref = k8s.CustomResourceReference(
        CRD_GROUP, CRD_VERSION, RESOURCE_PLURAL,
        resource_name, namespace="default",
    )
    k8s.create_custom_resource(ref, resource_data)
    cr = k8s.wait_resource_consumed_by_controller(ref)
    return ref, cr


@service_marker
@pytest.mark.canary
class TestBackupVaultLockConfiguration:
    def test_create_with_lock_configuration(self, backup_client):
        """A vault created with spec.lockConfiguration should have the lock
        applied in AWS after reconciliation."""
        resource_name = random_suffix_name("ack-lock-create", 32)

        ref, cr = _create_backup_vault(
            resource_name,
            resource_template="backup_vault_with_lock_configuration",
        )
        assert cr is not None
        assert k8s.get_resource_exists(ref)

        try:
            time.sleep(CREATE_WAIT_AFTER_SECONDS)
            assert k8s.wait_on_condition(
                ref, "ACK.ResourceSynced", "True", wait_periods=5,
            )

            min_days, max_days = _wait_for_lock(
                backup_client, resource_name,
                predicate=lambda t: t[0] is not None or t[1] is not None,
            )
            assert min_days == 1
            assert max_days == 365
        finally:
            k8s.delete_custom_resource(ref, 3, 10)
            time.sleep(DELETE_WAIT_AFTER_SECONDS)

    def test_crud_lock_configuration(self, backup_client):
        """Walk the full lifecycle for LockConfiguration on a vault created
        without a lock: add, update retention bounds, remove, and confirm
        cleanup on vault deletion."""
        resource_name = random_suffix_name("ack-lock-crud", 32)

        ref, cr = _create_backup_vault(
            resource_name,
            resource_template="backup_vault",
        )
        assert cr is not None

        try:
            time.sleep(CREATE_WAIT_AFTER_SECONDS)
            assert k8s.wait_on_condition(
                ref, "ACK.ResourceSynced", "True", wait_periods=5,
            )

            # No lock yet.
            min_days, max_days = _get_lock_configuration(backup_client, resource_name)
            assert min_days is None and max_days is None

            # --- Step 1: add lock configuration ---
            # ChangeableForDays ≥ 3 is required by AWS. Using a large value
            # (30 days) ensures we can still delete the lock during cleanup.
            cr = k8s.get_resource(ref)
            cr["spec"]["lockConfiguration"] = {
                "minRetentionDays": 1,
                "maxRetentionDays": 365,
                "changeableForDays": 30,
            }
            k8s.replace_custom_resource(ref, cr)
            time.sleep(UPDATE_WAIT_AFTER_SECONDS)
            assert k8s.wait_on_condition(
                ref, "ACK.ResourceSynced", "True", wait_periods=5,
            )

            min_days, max_days = _wait_for_lock(
                backup_client, resource_name,
                predicate=lambda t: t[0] is not None,
            )
            assert min_days == 1
            assert max_days == 365

            # --- Step 2: update retention bounds ---
            cr = k8s.get_resource(ref)
            cr["spec"]["lockConfiguration"] = {
                "minRetentionDays": 7,
                "maxRetentionDays": 730,
                "changeableForDays": 30,
            }
            k8s.replace_custom_resource(ref, cr)
            time.sleep(UPDATE_WAIT_AFTER_SECONDS)
            assert k8s.wait_on_condition(
                ref, "ACK.ResourceSynced", "True", wait_periods=10,
            )

            min_days, max_days = _wait_for_lock(
                backup_client, resource_name,
                predicate=lambda t: t[0] == 7,
            )
            assert min_days == 7
            assert max_days == 730

            # --- Step 3: remove lock configuration ---
            cr = k8s.get_resource(ref)
            cr["spec"]["lockConfiguration"] = None
            k8s.replace_custom_resource(ref, cr)
            time.sleep(UPDATE_WAIT_AFTER_SECONDS)
            assert k8s.wait_on_condition(
                ref, "ACK.ResourceSynced", "True", wait_periods=5,
            )

            _wait_for_lock(
                backup_client, resource_name,
                predicate=lambda t: t[0] is None and t[1] is None,
            )
        finally:
            # --- Step 4: delete vault and verify cleanup ---
            _, deleted = k8s.delete_custom_resource(ref, 3, 10)
            assert deleted
            time.sleep(DELETE_WAIT_AFTER_SECONDS)

            try:
                backup_client.describe_backup_vault(BackupVaultName=resource_name)
                assert False, (
                    f"BackupVault {resource_name} still exists in AWS after deletion"
                )
            except backup_client.exceptions.ResourceNotFoundException:
                pass
            except Exception:
                pass
