	// Extract the BackupVaultArn from the create response and set it in the status.
	// The CreateBackupVault API is synchronous, so the vault is immediately available.
	if ko.Status.ACKResourceMetadata == nil {
		ko.Status.ACKResourceMetadata = &ackv1alpha1.ResourceMetadata{}
	}
	if resp.BackupVaultArn != nil {
		arn := ackv1alpha1.AWSResourceName(*resp.BackupVaultArn)
		ko.Status.ACKResourceMetadata.ARN = &arn
	}

	// Set the ACK.ResourceSynced condition to True since BackupVault creation is synchronous
	// and the vault is immediately available after the API call succeeds.
	ackcondition.SetSynced(&resource{ko}, corev1.ConditionTrue, nil, nil)
