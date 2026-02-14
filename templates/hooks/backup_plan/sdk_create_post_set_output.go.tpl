	// Extract the BackupPlanId from the create response and set it in the status.
	// The CreateBackupPlan API returns the unique identifier for the backup plan.
	if resp.BackupPlanId != nil {
		ko.Status.BackupPlanID = resp.BackupPlanId
	}

	// Extract the VersionId from the create response and set it in the status.
	// Each update to a backup plan creates a new version, and this tracks the current version.
	if resp.VersionId != nil {
		ko.Status.VersionID = resp.VersionId
	}

	// Extract the BackupPlanArn from the create response and set it in ACKResourceMetadata.
	// This ARN uniquely identifies the backup plan resource in AWS.
	if ko.Status.ACKResourceMetadata == nil {
		ko.Status.ACKResourceMetadata = &ackv1alpha1.ResourceMetadata{}
	}
	if resp.BackupPlanArn != nil {
		arn := ackv1alpha1.AWSResourceName(*resp.BackupPlanArn)
		ko.Status.ACKResourceMetadata.ARN = &arn
	}

	// Set the ACK.ResourceSynced condition to True since BackupPlan creation is synchronous
	// and the plan is immediately available after the API call succeeds.
	ackcondition.SetSynced(&resource{ko}, corev1.ConditionTrue, nil, nil)
