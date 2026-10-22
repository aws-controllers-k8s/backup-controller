	// DescribeBackupVault serves every vault type, so a standard or
	// restore-access vault that happens to share this name would otherwise be
	// read back here as a logically air-gapped one. Treat a type mismatch as
	// not found rather than adopting the wrong vault.
	if string(resp.VaultType) != string(svcapitypes.VaultType_LOGICALLY_AIR_GAPPED_BACKUP_VAULT) {
		return nil, ackerr.NotFound
	}

	// DescribeBackupVault does not return tags, so we fetch them separately
	// using ListTags.
	if ko.Status.ACKResourceMetadata != nil && ko.Status.ACKResourceMetadata.ARN != nil {
		tagsResp, err := rm.sdkapi.ListTags(ctx, &svcsdk.ListTagsInput{
			ResourceArn: (*string)(ko.Status.ACKResourceMetadata.ARN),
		})
		rm.metrics.RecordAPICall("READ_ONE", "ListTags", err)
		if err != nil {
			return nil, err
		}
		if tagsResp.Tags != nil {
			ko.Spec.Tags = aws.StringMap(tagsResp.Tags)
		} else {
			ko.Spec.Tags = nil
		}
	}
