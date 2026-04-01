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

	ackcompare "github.com/aws-controllers-k8s/runtime/pkg/compare"
	"github.com/aws/aws-sdk-go-v2/aws"
	svcsdk "github.com/aws/aws-sdk-go-v2/service/backup"

	svcapitypes "github.com/aws-controllers-k8s/backup-controller/apis/v1alpha1"
	"github.com/aws-controllers-k8s/backup-controller/pkg/tags"
)

// syncTags calls TagResource/UntagResource as needed when tags have changed.
func (rm *resourceManager) syncTags(
	ctx context.Context,
	desired *resource,
	latest *resource,
	delta *ackcompare.Delta,
) error {
	if !delta.DifferentAt("Spec.Tags") {
		return nil
	}
	return tags.SyncTags(
		ctx, rm.sdkapi, rm.metrics,
		string(*desired.ko.Status.ACKResourceMetadata.ARN),
		desired.ko.Spec.Tags,
		latest.ko.Spec.Tags,
	)
}

// listTags calls ListTags and populates ko.Spec.Tags.
func (rm *resourceManager) listTags(
	ctx context.Context,
	ko *svcapitypes.BackupPlan,
) error {
	if ko.Status.ACKResourceMetadata == nil || ko.Status.ACKResourceMetadata.ARN == nil {
		return nil
	}
	resp, err := rm.sdkapi.ListTags(ctx, &svcsdk.ListTagsInput{
		ResourceArn: (*string)(ko.Status.ACKResourceMetadata.ARN),
	})
	rm.metrics.RecordAPICall("READ_ONE", "ListTags", err)
	if err != nil {
		return err
	}
	if resp.Tags != nil {
		ko.Spec.Tags = aws.StringMap(resp.Tags)
	} else {
		ko.Spec.Tags = nil
	}
	return nil
}
