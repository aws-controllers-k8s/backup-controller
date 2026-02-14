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

"""Utility functions to help processing Kubernetes resource conditions"""

import pytest

from acktest.k8s import resource as k8s

CONDITION_TYPE_RESOURCE_SYNCED = "ACK.ResourceSynced"
CONDITION_TYPE_TERMINAL = "ACK.Terminal"


def assert_type_status(
    ref: k8s.CustomResourceReference,
    cond_type_match: str = CONDITION_TYPE_RESOURCE_SYNCED,
    cond_status_match: bool = True,
):
    cond = k8s.get_resource_condition(ref, cond_type_match)
    if cond is None:
        msg = (f"Failed to find {cond_type_match} condition in "
               f"resource {ref}")
        pytest.fail(msg)

    cond_status = cond.get('status', None)
    if str(cond_status) != str(cond_status_match):
        msg = (f"Expected {cond_type_match} condition to "
               f"have status {cond_status_match} but found {cond_status}")
        pytest.fail(msg)


def assert_synced(ref: k8s.CustomResourceReference):
    assert_type_status(ref, CONDITION_TYPE_RESOURCE_SYNCED, True)


def assert_not_synced(ref: k8s.CustomResourceReference):
    assert_type_status(ref, CONDITION_TYPE_RESOURCE_SYNCED, False)
