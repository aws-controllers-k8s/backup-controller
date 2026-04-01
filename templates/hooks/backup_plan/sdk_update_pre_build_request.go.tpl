	if err := rm.syncTags(ctx, desired, latest, delta); err != nil {
		return nil, err
	}
	// If only tags changed, no need to call UpdateBackupPlan.
	if !delta.DifferentExcept("Spec.Tags") {
		return desired, nil
	}
