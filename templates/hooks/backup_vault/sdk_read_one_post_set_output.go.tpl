	// DescribeBackupVault does not return tags, so we fetch them separately
	// using ListTags.
	if ko.Status.ACKResourceMetadata != nil && ko.Status.ACKResourceMetadata.ARN != nil {
		tagsResp, err := rm.sdkapi.ListTags(ctx, &svcsdk.ListTagsInput{
			ResourceArn: (*string)(ko.Status.ACKResourceMetadata.ARN),
		})
		rm.metrics.RecordAPICall("GET_TAGS", "ListTags", err)
		if err != nil {
			return nil, err
		}
		if tagsResp.Tags != nil {
			ko.Spec.Tags = aws.StringMap(tagsResp.Tags)
		} else {
			ko.Spec.Tags = nil
		}
	}
