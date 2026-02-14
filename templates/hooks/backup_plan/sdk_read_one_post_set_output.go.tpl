	// Sync versionID from get response.
	// This is a read-only status field that reflects the current version of the backup plan.
	// Each update to a backup plan creates a new version.
	if resp.VersionId != nil {
		ko.Status.VersionID = resp.VersionId
	}

	// Sync creationDate from get response.
	// This is a read-only status field that reflects when the backup plan was created.
	if resp.CreationDate != nil {
		ko.Status.CreationDate = &metav1.Time{Time: *resp.CreationDate}
	}
