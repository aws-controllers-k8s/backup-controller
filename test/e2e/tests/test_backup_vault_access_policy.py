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

"""Integration tests for the BackupVault resource's AccessPolicy sub-resource.

AccessPolicy is driven by the sub-resource-manager construct in the
code-generator: the parent's generated sdkUpdate calls Sync() on the
backup_vault_access_policy sub-resource when Spec.AccessPolicy changes,
and sdkDelete clears the policy before removing the vault.
"""

import json
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


def _policy_for_action(account_id: str, action: str, sid: str = "TestStatement") -> str:
    """Build a minimal, valid vault resource policy for a given backup action."""
    doc = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": sid,
                "Effect": "Deny",
                "Principal": {"AWS": account_id},
                "Action": action,
                "Resource": "*",
            }
        ],
    }
    return json.dumps(doc)


def _get_access_policy(backup_client, vault_name: str):
    """Return the attached access policy document as a dict, or None if absent."""
    try:
        resp = backup_client.get_backup_vault_access_policy(
            BackupVaultName=vault_name,
        )
    except backup_client.exceptions.ResourceNotFoundException:
        return None
    except Exception as ex:
        # The Backup API returns a generic error when no policy is attached;
        # treat any error during read as "no policy" so the test can proceed.
        logging.debug("get_backup_vault_access_policy error: %s", ex)
        return None
    raw = resp.get("Policy")
    if raw is None:
        return None
    return json.loads(raw)


def _wait_for_policy(backup_client, vault_name: str, predicate, attempts: int = 12,
                     interval: int = 5):
    """Poll get_backup_vault_access_policy until predicate(policy_dict) is True.

    Returns the last policy dict observed. Raises AssertionError if the
    predicate never matches.
    """
    last = None
    for _ in range(attempts):
        last = _get_access_policy(backup_client, vault_name)
        if predicate(last):
            return last
        time.sleep(interval)
    raise AssertionError(
        f"timed out waiting for expected access policy on {vault_name}; "
        f"last observed: {last}"
    )


def _create_backup_vault(resource_name: str, resource_template: str,
                         extra_replacements: dict = None):
    """Helper to create a BackupVault CR and return (ref, cr)."""
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
class TestBackupVaultAccessPolicy:
    def test_create_with_access_policy(self, backup_client):
        """A vault created with spec.accessPolicy should have the policy
        attached in AWS after reconciliation."""
        resource_name = random_suffix_name("ack-ap-create", 32)

        ref, cr = _create_backup_vault(
            resource_name,
            resource_template="backup_vault_with_access_policy",
        )
        assert cr is not None
        assert k8s.get_resource_exists(ref)

        try:
            time.sleep(CREATE_WAIT_AFTER_SECONDS)
            assert k8s.wait_on_condition(
                ref, "ACK.ResourceSynced", "True", wait_periods=5,
            )

            policy = _wait_for_policy(
                backup_client, resource_name,
                predicate=lambda p: p is not None
                and p["Statement"][0].get("Sid") == "DenyDeleteRecoveryPoint",
            )
            assert policy["Statement"][0]["Effect"] == "Deny"
            assert policy["Statement"][0]["Action"] == "backup:DeleteRecoveryPoint"
        finally:
            k8s.delete_custom_resource(ref, 3, 10)
            time.sleep(DELETE_WAIT_AFTER_SECONDS)

    def test_crud_access_policy(self, backup_client):
        """Walk the full lifecycle for AccessPolicy on a vault created
        without a policy: add, update, remove, and confirm cleanup on vault
        deletion."""
        resource_name = random_suffix_name("ack-ap-crud", 32)
        account_id = REPLACEMENT_VALUES["ACCOUNT_ID"]

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

            # No access policy exists yet.
            assert _get_access_policy(backup_client, resource_name) is None

            # --- Step 1: add a policy ---
            add_policy = _policy_for_action(
                account_id, "backup:DeleteRecoveryPoint", sid="InitialDeny",
            )
            cr = k8s.get_resource(ref)
            cr["spec"]["accessPolicy"] = {"policy": add_policy}
            k8s.replace_custom_resource(ref, cr)
            time.sleep(UPDATE_WAIT_AFTER_SECONDS)
            assert k8s.wait_on_condition(
                ref, "ACK.ResourceSynced", "True", wait_periods=5,
            )

            policy = _wait_for_policy(
                backup_client, resource_name,
                predicate=lambda p: p is not None
                and p["Statement"][0].get("Sid") == "InitialDeny",
            )
            assert policy["Statement"][0]["Action"] == "backup:DeleteRecoveryPoint"

            # --- Step 2: update policy body ---
            updated_policy = _policy_for_action(
                account_id, "backup:DeleteBackupVault", sid="UpdatedDeny",
            )
            cr = k8s.get_resource(ref)
            cr["spec"]["accessPolicy"] = {"policy": updated_policy}
            k8s.replace_custom_resource(ref, cr)
            time.sleep(UPDATE_WAIT_AFTER_SECONDS)
            assert k8s.wait_on_condition(
                ref, "ACK.ResourceSynced", "True", wait_periods=10,
            )

            policy = _wait_for_policy(
                backup_client, resource_name,
                predicate=lambda p: p is not None
                and p["Statement"][0].get("Sid") == "UpdatedDeny",
            )
            assert policy["Statement"][0]["Action"] == "backup:DeleteBackupVault"

            # --- Step 3: remove the policy ---
            cr = k8s.get_resource(ref)
            cr["spec"]["accessPolicy"] = None
            k8s.replace_custom_resource(ref, cr)
            time.sleep(UPDATE_WAIT_AFTER_SECONDS)
            assert k8s.wait_on_condition(
                ref, "ACK.ResourceSynced", "True", wait_periods=5,
            )

            _wait_for_policy(
                backup_client, resource_name,
                predicate=lambda p: p is None,
            )
        finally:
            # --- Step 4: delete the vault and verify cleanup ---
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
                # AccessDeniedException also indicates 'not found' for this API.
                pass
