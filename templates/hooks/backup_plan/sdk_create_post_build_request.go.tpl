	// BackupPlanTags is outside the input_wrapper_field_path (BackupPlan).
	// Wire Spec.Tags into the SDK input manually.
	if desired.ko.Spec.Tags != nil {
		input.BackupPlanTags = aws.ToStringMap(desired.ko.Spec.Tags)
	}
