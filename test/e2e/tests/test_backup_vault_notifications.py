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

"""Integration tests for the BackupVault resource's Notifications sub-resource.

Notifications is driven by the sub-resource-manager construct in the
code-generator: the parent's generated sdkUpdate calls Sync() on the
backup_vault_notifications sub-resource when Spec.Notifications changes,
and sdkDelete clears the notifications before removing the vault.
"""

import logging
import time

import boto3
import pytest
from acktest.k8s import resource as k8s
from acktest.resources import random_suffix_name

from e2e import CRD_GROUP, CRD_VERSION, load_backup_resource, service_marker
from e2e.replacement_values import REPLACEMENT_VALUES

RESOURCE_PLURAL = "backupvaults"

CREATE_WAIT_AFTER_SECONDS = 10
UPDATE_WAIT_AFTER_SECONDS = 10
DELETE_WAIT_AFTER_SECONDS = 10


def _get_notifications(backup_client, vault_name: str):
    """Return (sns_topic_arn, events) for the vault, or (None, None) if absent."""
    try:
        resp = backup_client.get_backup_vault_notifications(
            BackupVaultName=vault_name,
        )
    except backup_client.exceptions.ResourceNotFoundException:
        return None, None
    except Exception as ex:
        logging.debug("get_backup_vault_notifications error: %s", ex)
        return None, None
    return resp.get("SNSTopicArn"), resp.get("BackupVaultEvents", [])


def _wait_for_notifications(backup_client, vault_name: str, predicate,
                             attempts: int = 12, interval: int = 5):
    """Poll get_backup_vault_notifications until predicate((arn, events)) is True."""
    last = (None, None)
    for _ in range(attempts):
        last = _get_notifications(backup_client, vault_name)
        if predicate(last):
            return last
        time.sleep(interval)
    raise AssertionError(
        f"timed out waiting for expected notifications on {vault_name}; "
        f"last observed: {last}"
    )


def _create_sns_topic(region: str, name: str) -> str:
    """Create a minimal SNS topic and return its ARN."""
    sns = boto3.client("sns", region_name=region)
    resp = sns.create_topic(Name=name)
    return resp["TopicArn"]


def _delete_sns_topic(region: str, arn: str):
    sns = boto3.client("sns", region_name=region)
    try:
        sns.delete_topic(TopicArn=arn)
    except Exception:
        pass


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
class TestBackupVaultNotifications:
    def test_create_with_notifications(self, backup_client):
        """A vault created with spec.notifications should have the SNS
        subscription attached in AWS after reconciliation."""
        resource_name = random_suffix_name("ack-notif-create", 32)
        region = REPLACEMENT_VALUES.get("AWS_REGION", "us-west-2")
        topic_name = random_suffix_name("ack-notif-topic", 32)
        topic_arn = _create_sns_topic(region, topic_name)

        try:
            ref, cr = _create_backup_vault(
                resource_name,
                resource_template="backup_vault_with_notifications",
                extra_replacements={"SNS_TOPIC_ARN": topic_arn},
            )
            assert cr is not None
            assert k8s.get_resource_exists(ref)

            try:
                time.sleep(CREATE_WAIT_AFTER_SECONDS)
                assert k8s.wait_on_condition(
                    ref, "ACK.ResourceSynced", "True", wait_periods=5,
                )

                arn, events = _wait_for_notifications(
                    backup_client, resource_name,
                    predicate=lambda t: t[0] is not None,
                )
                assert arn == topic_arn
                assert "BACKUP_JOB_STARTED" in events
                assert "BACKUP_JOB_COMPLETED" in events
            finally:
                k8s.delete_custom_resource(ref, 3, 10)
                time.sleep(DELETE_WAIT_AFTER_SECONDS)
        finally:
            _delete_sns_topic(region, topic_arn)

    def test_crud_notifications(self, backup_client):
        """Walk the full lifecycle for Notifications on a vault created
        without notifications: add, update events, remove, and confirm
        cleanup on vault deletion."""
        resource_name = random_suffix_name("ack-notif-crud", 32)
        region = REPLACEMENT_VALUES.get("AWS_REGION", "us-west-2")
        topic_name = random_suffix_name("ack-notif-topic", 32)
        topic_arn = _create_sns_topic(region, topic_name)

        try:
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

                # No notifications yet.
                arn, _ = _get_notifications(backup_client, resource_name)
                assert arn is None

                # --- Step 1: add notifications ---
                cr = k8s.get_resource(ref)
                cr["spec"]["notifications"] = {
                    "snsTopicARN": topic_arn,
                    "events": ["BACKUP_JOB_STARTED", "BACKUP_JOB_COMPLETED"],
                }
                k8s.replace_custom_resource(ref, cr)
                time.sleep(UPDATE_WAIT_AFTER_SECONDS)
                assert k8s.wait_on_condition(
                    ref, "ACK.ResourceSynced", "True", wait_periods=5,
                )

                arn, events = _wait_for_notifications(
                    backup_client, resource_name,
                    predicate=lambda t: t[0] is not None,
                )
                assert arn == topic_arn
                assert "BACKUP_JOB_STARTED" in events

                # --- Step 2: update event list ---
                cr = k8s.get_resource(ref)
                cr["spec"]["notifications"] = {
                    "snsTopicARN": topic_arn,
                    "events": ["RESTORE_JOB_COMPLETED"],
                }
                k8s.replace_custom_resource(ref, cr)
                time.sleep(UPDATE_WAIT_AFTER_SECONDS)
                assert k8s.wait_on_condition(
                    ref, "ACK.ResourceSynced", "True", wait_periods=10,
                )

                arn, events = _wait_for_notifications(
                    backup_client, resource_name,
                    predicate=lambda t: t[0] is not None
                    and "RESTORE_JOB_COMPLETED" in (t[1] or []),
                )
                assert arn == topic_arn
                assert "RESTORE_JOB_COMPLETED" in events
                assert "BACKUP_JOB_STARTED" not in events

                # --- Step 3: remove notifications ---
                cr = k8s.get_resource(ref)
                cr["spec"]["notifications"] = None
                k8s.replace_custom_resource(ref, cr)
                time.sleep(UPDATE_WAIT_AFTER_SECONDS)
                assert k8s.wait_on_condition(
                    ref, "ACK.ResourceSynced", "True", wait_periods=5,
                )

                _wait_for_notifications(
                    backup_client, resource_name,
                    predicate=lambda t: t[0] is None,
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
        finally:
            _delete_sns_topic(region, topic_arn)
