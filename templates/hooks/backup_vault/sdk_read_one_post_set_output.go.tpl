	// DescribeBackupVault serves every vault type, so a logically air-gapped or
	// restore-access vault sharing this name would otherwise be read back here
	// as a standard vault. Treat a known mismatch as not found. An empty
	// VaultType is tolerated rather than rejected: we have not confirmed that
	// DescribeBackupVault populates it for standard vaults, and failing those
	// reads would be worse than missing the guard.
	if resp.VaultType != "" &&
		string(resp.VaultType) != string(svcapitypes.VaultType_BACKUP_VAULT) {
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
