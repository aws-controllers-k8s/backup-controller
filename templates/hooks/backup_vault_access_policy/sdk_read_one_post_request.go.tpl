	// GetBackupVaultAccessPolicy returns ResourceNotFoundException both
	// when the vault does not exist and when the vault exists but has no
	// policy attached. The generated sub-resource sdkFind only recognises
	// an "UNKNOWN" error code as 404, so we translate the real error here
	// (before the generator's own error check) into ackerr.NotFound. That
	// lets mgr.Get() clear Spec.AccessPolicy and return success instead of
	// stalling the reconcile loop on every poll.
	if err != nil {
		var awsErr smithy.APIError
		if errors.As(err, &awsErr) && awsErr.ErrorCode() == "ResourceNotFoundException" {
			err = ackerr.NotFound
		}
	}
