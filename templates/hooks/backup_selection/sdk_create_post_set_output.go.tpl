	// Extract the SelectionId from the create response and set it in the status.
	// The CreateBackupSelection API returns the unique identifier for the backup selection.
	if resp.SelectionId != nil {
		ko.Status.SelectionID = resp.SelectionId
	}

	// Set the ACK.ResourceSynced condition to True since BackupSelection creation is synchronous
	// and the selection is immediately available after the API call succeeds.
	ackcondition.SetSynced(&resource{ko}, corev1.ConditionTrue, nil, nil)
