	// Sync numberOfRecoveryPoints from describe response.
	// This is a read-only status field that reflects the current count of recovery points in the vault.
	ko.Status.NumberOfRecoveryPoints = &resp.NumberOfRecoveryPoints

	// Sync locked status from describe response.
	// This indicates whether Backup Vault Lock is currently protecting the vault.
	if resp.Locked != nil {
		ko.Status.Locked = resp.Locked
	}

	// Sync lockDate from describe response.
	// This is the date and time when Vault Lock configuration becomes immutable.
	if resp.LockDate != nil {
		ko.Status.LockDate = &metav1.Time{Time: *resp.LockDate}
	}
