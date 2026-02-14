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

package backup_plan

import (
	"context"

	ackv1alpha1 "github.com/aws-controllers-k8s/runtime/apis/core/v1alpha1"
	ackcompare "github.com/aws-controllers-k8s/runtime/pkg/compare"
	ackrtlog "github.com/aws-controllers-k8s/runtime/pkg/runtime/log"
	"github.com/aws/aws-sdk-go-v2/aws"
	svcsdk "github.com/aws/aws-sdk-go-v2/service/backup"
	svcsdktypes "github.com/aws/aws-sdk-go-v2/service/backup/types"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"

	svcapitypes "github.com/aws-controllers-k8s/backup-controller/apis/v1alpha1"
)

// customUpdateBackupPlan handles the update of a BackupPlan resource.
// It calls the UpdateBackupPlan API and updates the versionID in status.
func (rm *resourceManager) customUpdateBackupPlan(
	ctx context.Context,
	desired *resource,
	latest *resource,
	delta *ackcompare.Delta,
) (*resource, error) {
	var err error
	rlog := ackrtlog.FromContext(ctx)
	exit := rlog.Trace("rm.customUpdateBackupPlan")
	defer func() {
		exit(err)
	}()

	// Build the update request payload
	input, err := rm.newUpdateRequestPayload(desired)
	if err != nil {
		return nil, err
	}

	// Call the UpdateBackupPlan API
	var resp *svcsdk.UpdateBackupPlanOutput
	resp, err = rm.sdkapi.UpdateBackupPlan(ctx, input)
	rm.metrics.RecordAPICall("UPDATE", "UpdateBackupPlan", err)
	if err != nil {
		return nil, err
	}

	// Merge the response into the desired resource
	ko := desired.ko.DeepCopy()

	// Update status fields from the response
	if resp.AdvancedBackupSettings != nil {
		f0 := []*svcapitypes.AdvancedBackupSetting{}
		for _, f0iter := range resp.AdvancedBackupSettings {
			f0elem := &svcapitypes.AdvancedBackupSetting{}
			if f0iter.BackupOptions != nil {
				f0elem.BackupOptions = aws.StringMap(f0iter.BackupOptions)
			}
			if f0iter.ResourceType != nil {
				f0elem.ResourceType = f0iter.ResourceType
			}
			f0 = append(f0, f0elem)
		}
		ko.Status.AdvancedBackupSettings = f0
	}

	if ko.Status.ACKResourceMetadata == nil {
		ko.Status.ACKResourceMetadata = &ackv1alpha1.ResourceMetadata{}
	}
	if resp.BackupPlanArn != nil {
		arn := ackv1alpha1.AWSResourceName(*resp.BackupPlanArn)
		ko.Status.ACKResourceMetadata.ARN = &arn
	}
	if resp.BackupPlanId != nil {
		ko.Status.BackupPlanID = resp.BackupPlanId
	}
	if resp.CreationDate != nil {
		ko.Status.CreationDate = &metav1.Time{Time: *resp.CreationDate}
	}
	if resp.VersionId != nil {
		ko.Status.VersionID = resp.VersionId
	}

	rm.setStatusDefaults(ko)

	return &resource{ko}, nil
}

// newUpdateRequestPayload returns an SDK-specific struct for the HTTP request
// payload of the Update API call for the resource
func (rm *resourceManager) newUpdateRequestPayload(
	r *resource,
) (*svcsdk.UpdateBackupPlanInput, error) {
	res := &svcsdk.UpdateBackupPlanInput{}

	// BackupPlanId is required for update
	if r.ko.Status.BackupPlanID != nil {
		res.BackupPlanId = r.ko.Status.BackupPlanID
	}

	// Build the BackupPlan input from the spec
	if r.ko.Spec.BackupPlan != nil {
		f0 := &svcsdktypes.BackupPlanInput{}
		if r.ko.Spec.BackupPlan.AdvancedBackupSettings != nil {
			f0f0 := []svcsdktypes.AdvancedBackupSetting{}
			for _, f0f0iter := range r.ko.Spec.BackupPlan.AdvancedBackupSettings {
				f0f0elem := svcsdktypes.AdvancedBackupSetting{}
				if f0f0iter.BackupOptions != nil {
					f0f0elem.BackupOptions = aws.ToStringMap(f0f0iter.BackupOptions)
				}
				if f0f0iter.ResourceType != nil {
					f0f0elem.ResourceType = f0f0iter.ResourceType
				}
				f0f0 = append(f0f0, f0f0elem)
			}
			f0.AdvancedBackupSettings = f0f0
		}
		if r.ko.Spec.BackupPlan.BackupPlanName != nil {
			f0.BackupPlanName = r.ko.Spec.BackupPlan.BackupPlanName
		}
		if r.ko.Spec.BackupPlan.Rules != nil {
			f0f2 := []svcsdktypes.BackupRuleInput{}
			for _, f0f2iter := range r.ko.Spec.BackupPlan.Rules {
				f0f2elem := svcsdktypes.BackupRuleInput{}
				if f0f2iter.CompletionWindowMinutes != nil {
					f0f2elem.CompletionWindowMinutes = f0f2iter.CompletionWindowMinutes
				}
				if f0f2iter.CopyActions != nil {
					f0f2elemf1 := []svcsdktypes.CopyAction{}
					for _, f0f2elemf1iter := range f0f2iter.CopyActions {
						f0f2elemf1elem := svcsdktypes.CopyAction{}
						if f0f2elemf1iter.DestinationBackupVaultARN != nil {
							f0f2elemf1elem.DestinationBackupVaultArn = f0f2elemf1iter.DestinationBackupVaultARN
						}
						if f0f2elemf1iter.Lifecycle != nil {
							f0f2elemf1elemf1 := &svcsdktypes.Lifecycle{}
							if f0f2elemf1iter.Lifecycle.DeleteAfterDays != nil {
								f0f2elemf1elemf1.DeleteAfterDays = f0f2elemf1iter.Lifecycle.DeleteAfterDays
							}
							if f0f2elemf1iter.Lifecycle.MoveToColdStorageAfterDays != nil {
								f0f2elemf1elemf1.MoveToColdStorageAfterDays = f0f2elemf1iter.Lifecycle.MoveToColdStorageAfterDays
							}
							f0f2elemf1elem.Lifecycle = f0f2elemf1elemf1
						}
						f0f2elemf1 = append(f0f2elemf1, f0f2elemf1elem)
					}
					f0f2elem.CopyActions = f0f2elemf1
				}
				if f0f2iter.EnableContinuousBackup != nil {
					f0f2elem.EnableContinuousBackup = f0f2iter.EnableContinuousBackup
				}
				if f0f2iter.Lifecycle != nil {
					f0f2elemf4 := &svcsdktypes.Lifecycle{}
					if f0f2iter.Lifecycle.DeleteAfterDays != nil {
						f0f2elemf4.DeleteAfterDays = f0f2iter.Lifecycle.DeleteAfterDays
					}
					if f0f2iter.Lifecycle.MoveToColdStorageAfterDays != nil {
						f0f2elemf4.MoveToColdStorageAfterDays = f0f2iter.Lifecycle.MoveToColdStorageAfterDays
					}
					f0f2elem.Lifecycle = f0f2elemf4
				}
				if f0f2iter.RecoveryPointTags != nil {
					f0f2elem.RecoveryPointTags = aws.ToStringMap(f0f2iter.RecoveryPointTags)
				}
				if f0f2iter.RuleName != nil {
					f0f2elem.RuleName = f0f2iter.RuleName
				}
				if f0f2iter.ScheduleExpression != nil {
					f0f2elem.ScheduleExpression = f0f2iter.ScheduleExpression
				}
				if f0f2iter.StartWindowMinutes != nil {
					f0f2elem.StartWindowMinutes = f0f2iter.StartWindowMinutes
				}
				if f0f2iter.TargetBackupVaultName != nil {
					f0f2elem.TargetBackupVaultName = f0f2iter.TargetBackupVaultName
				}
				f0f2 = append(f0f2, f0f2elem)
			}
			f0.Rules = f0f2
		}
		res.BackupPlan = f0
	}

	return res, nil
}
