// Copyright Amazon.com Inc. or its affiliates. All Rights Reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License"). You may
// not use this file except in compliance with the License. A copy of the
// License is located at
//
//     http://aws.amazon.com/apache2.0/
//
// or in the "license" file accompanying this file. This file is distributed
// on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
// express or implied. See the License for the specific language governing
// permissions and limitations under the License.

package lock_configuration

import (
	"context"
	"errors"

	ackerr "github.com/aws-controllers-k8s/runtime/pkg/errors"
	svcsdk "github.com/aws/aws-sdk-go-v2/service/backup"
	smithy "github.com/aws/smithy-go"
)

// customFindLockConfiguration reads the lock configuration from
// DescribeBackupVault. There is no dedicated GetBackupVaultLockConfiguration
// API — the lock settings (MinRetentionDays, MaxRetentionDays) are returned
// as part of the vault description.
//
// Returns ackerr.NotFound when:
//   - The vault does not exist.
//   - The vault exists but has no lock configuration applied
//     (both MinRetentionDays and MaxRetentionDays are nil/zero).
func (rm *resourceManager) customFindLockConfiguration(
	ctx context.Context,
	r *resource,
) (*resource, error) {
	if r.ko.Spec.BackupVaultName == nil {
		return nil, ackerr.NotFound
	}

	resp, err := rm.sdkapi.DescribeBackupVault(ctx, &svcsdk.DescribeBackupVaultInput{
		BackupVaultName: r.ko.Spec.BackupVaultName,
	})
	rm.metrics.RecordAPICall("READ_ONE", "DescribeBackupVault", err)
	if err != nil {
		var awsErr smithy.APIError
		if errors.As(err, &awsErr) {
			switch awsErr.ErrorCode() {
			case "ResourceNotFoundException", "AccessDeniedException":
				return nil, ackerr.NotFound
			}
		}
		return nil, err
	}

	// If neither retention bound is set, no lock configuration exists.
	if resp.MinRetentionDays == nil && resp.MaxRetentionDays == nil {
		return nil, ackerr.NotFound
	}

	ko := r.ko.DeepCopy()
	ko.Spec.MinRetentionDays = resp.MinRetentionDays
	ko.Spec.MaxRetentionDays = resp.MaxRetentionDays
	// ChangeableForDays is write-only — not returned by DescribeBackupVault.
	// Leave it nil so compare.is_ignored prevents spurious drift detection.
	ko.Spec.ChangeableForDays = nil

	if resp.BackupVaultName != nil {
		ko.Spec.BackupVaultName = resp.BackupVaultName
	}

	rm.setStatusDefaults(ko)
	return &resource{ko: ko}, nil
}
