	// GetBackupVaultNotifications returns ResourceNotFoundException both
	// when the vault does not exist and when the vault exists but has no
	// notifications configured. Translate into ackerr.NotFound so
	// mgr.Get() clears Spec.Notifications and returns success instead of
	// stalling the reconcile loop on every poll.
	if err != nil {
		var awsErr smithy.APIError
		if errors.As(err, &awsErr) && awsErr.ErrorCode() == "ResourceNotFoundException" {
			err = ackerr.NotFound
		}
	}
