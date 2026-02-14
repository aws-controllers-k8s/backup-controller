# IAM Permissions for AWS Backup Controller

This document describes the IAM permissions required for the AWS Backup ACK controller and the resources it manages.

## Controller IAM Permissions

The ACK Backup controller requires IAM permissions to manage AWS Backup resources. These permissions should be attached to the IAM role used by the controller (via IRSA, instance profile, or other methods).

### Minimum Required Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BackupVaultPermissions",
      "Effect": "Allow",
      "Action": [
        "backup:CreateBackupVault",
        "backup:DeleteBackupVault",
        "backup:DescribeBackupVault",
        "backup:PutBackupVaultAccessPolicy",
        "backup:DeleteBackupVaultAccessPolicy",
        "backup:GetBackupVaultAccessPolicy",
        "backup:PutBackupVaultLockConfiguration",
        "backup:DeleteBackupVaultLockConfiguration",
        "backup:GetBackupVaultNotifications",
        "backup:PutBackupVaultNotifications",
        "backup:DeleteBackupVaultNotifications"
      ],
      "Resource": "arn:aws:backup:*:*:backup-vault:*"
    },
    {
      "Sid": "BackupPlanPermissions",
      "Effect": "Allow",
      "Action": [
        "backup:CreateBackupPlan",
        "backup:DeleteBackupPlan",
        "backup:GetBackupPlan",
        "backup:UpdateBackupPlan",
        "backup:ListBackupPlans"
      ],
      "Resource": "arn:aws:backup:*:*:backup-plan:*"
    },
    {
      "Sid": "BackupSelectionPermissions",
      "Effect": "Allow",
      "Action": [
        "backup:CreateBackupSelection",
        "backup:DeleteBackupSelection",
        "backup:GetBackupSelection",
        "backup:ListBackupSelections"
      ],
      "Resource": "arn:aws:backup:*:*:backup-plan:*"
    },
    {
      "Sid": "TaggingPermissions",
      "Effect": "Allow",
      "Action": [
        "backup:TagResource",
        "backup:UntagResource",
        "backup:ListTags"
      ],
      "Resource": "*"
    },
    {
      "Sid": "IAMPassRole",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "iam:PassedToService": "backup.amazonaws.com"
        }
      }
    }
  ]
}
```

### Restricting Permissions by Resource

For production environments, you may want to restrict permissions to specific resources:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "backup:CreateBackupVault",
        "backup:DeleteBackupVault",
        "backup:DescribeBackupVault"
      ],
      "Resource": "arn:aws:backup:us-west-2:123456789012:backup-vault:k8s-*"
    }
  ]
}
```

## BackupSelection IAM Role Requirements

When creating a `BackupSelection` resource, you must specify an IAM role ARN in `spec.backupSelection.iamRoleARN`. This role is used by AWS Backup to perform backup operations on the selected resources.

### Trust Policy

The IAM role must have a trust policy that allows AWS Backup to assume it:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "backup.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

### Permissions by Resource Type

#### DynamoDB Tables

For backing up DynamoDB tables:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DynamoDBBackupPermissions",
      "Effect": "Allow",
      "Action": [
        "dynamodb:CreateBackup",
        "dynamodb:DescribeTable",
        "dynamodb:ListTagsOfResource"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/*"
    },
    {
      "Sid": "DynamoDBRestorePermissions",
      "Effect": "Allow",
      "Action": [
        "dynamodb:RestoreTableFromBackup",
        "dynamodb:DeleteBackup",
        "dynamodb:DescribeBackup"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/*/backup/*"
    },
    {
      "Sid": "BackupVaultPermissions",
      "Effect": "Allow",
      "Action": [
        "backup:DescribeBackupVault",
        "backup:CopyIntoBackupVault"
      ],
      "Resource": "arn:aws:backup:*:*:backup-vault:*"
    }
  ]
}
```

#### EBS Volumes

For backing up EBS volumes:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "EBSBackupPermissions",
      "Effect": "Allow",
      "Action": [
        "ec2:CreateSnapshot",
        "ec2:CreateSnapshots",
        "ec2:DescribeVolumes",
        "ec2:DescribeSnapshots",
        "ec2:DeleteSnapshot",
        "ec2:CreateTags",
        "ec2:DeleteTags"
      ],
      "Resource": "*"
    },
    {
      "Sid": "BackupVaultPermissions",
      "Effect": "Allow",
      "Action": [
        "backup:DescribeBackupVault",
        "backup:CopyIntoBackupVault"
      ],
      "Resource": "arn:aws:backup:*:*:backup-vault:*"
    }
  ]
}
```

#### RDS Databases

For backing up RDS databases:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "RDSBackupPermissions",
      "Effect": "Allow",
      "Action": [
        "rds:CreateDBSnapshot",
        "rds:CreateDBClusterSnapshot",
        "rds:DescribeDBSnapshots",
        "rds:DescribeDBClusterSnapshots",
        "rds:DescribeDBInstances",
        "rds:DescribeDBClusters",
        "rds:ListTagsForResource",
        "rds:AddTagsToResource",
        "rds:DeleteDBSnapshot",
        "rds:DeleteDBClusterSnapshot"
      ],
      "Resource": "*"
    },
    {
      "Sid": "BackupVaultPermissions",
      "Effect": "Allow",
      "Action": [
        "backup:DescribeBackupVault",
        "backup:CopyIntoBackupVault"
      ],
      "Resource": "arn:aws:backup:*:*:backup-vault:*"
    }
  ]
}
```

#### EFS File Systems

For backing up EFS file systems:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "EFSBackupPermissions",
      "Effect": "Allow",
      "Action": [
        "elasticfilesystem:Backup",
        "elasticfilesystem:DescribeFileSystems"
      ],
      "Resource": "arn:aws:elasticfilesystem:*:*:file-system/*"
    },
    {
      "Sid": "BackupVaultPermissions",
      "Effect": "Allow",
      "Action": [
        "backup:DescribeBackupVault",
        "backup:CopyIntoBackupVault"
      ],
      "Resource": "arn:aws:backup:*:*:backup-vault:*"
    }
  ]
}
```

### AWS Managed Policies

AWS provides managed policies that can be used for common backup scenarios:

| Policy Name | Description |
|-------------|-------------|
| `AWSBackupServiceRolePolicyForBackup` | Provides permissions for AWS Backup to create backups |
| `AWSBackupServiceRolePolicyForRestores` | Provides permissions for AWS Backup to restore backups |
| `AWSBackupFullAccess` | Full access to AWS Backup (for administrators) |
| `AWSBackupOperatorAccess` | Operator access to AWS Backup |

Example using managed policy:

```bash
aws iam attach-role-policy \
  --role-name AWSBackupDefaultServiceRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup
```

## Cross-Account Backup Permissions

For cross-account backup scenarios (using copy actions), additional permissions are required:

### Source Account

The backup role in the source account needs:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CrossAccountCopy",
      "Effect": "Allow",
      "Action": [
        "backup:CopyIntoBackupVault",
        "backup:StartCopyJob"
      ],
      "Resource": "arn:aws:backup:*:DESTINATION_ACCOUNT_ID:backup-vault:*"
    }
  ]
}
```

### Destination Account

The destination vault must have an access policy allowing the source account:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowCrossAccountCopy",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::SOURCE_ACCOUNT_ID:root"
      },
      "Action": "backup:CopyIntoBackupVault",
      "Resource": "*"
    }
  ]
}
```

## KMS Permissions for Encrypted Vaults

If using a customer-managed KMS key for vault encryption:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "KMSPermissions",
      "Effect": "Allow",
      "Action": [
        "kms:Encrypt",
        "kms:Decrypt",
        "kms:ReEncrypt*",
        "kms:GenerateDataKey*",
        "kms:DescribeKey",
        "kms:CreateGrant"
      ],
      "Resource": "arn:aws:kms:*:*:key/*",
      "Condition": {
        "StringEquals": {
          "kms:ViaService": "backup.*.amazonaws.com"
        }
      }
    }
  ]
}
```

## Setting Up IRSA (IAM Roles for Service Accounts)

For EKS clusters, use IRSA to provide IAM credentials to the controller:

1. Create an IAM OIDC provider for your cluster:

   ```bash
   eksctl utils associate-iam-oidc-provider \
     --cluster <cluster-name> \
     --approve
   ```

2. Create the IAM role with the controller policy:

   ```bash
   eksctl create iamserviceaccount \
     --name ack-backup-controller \
     --namespace ack-system \
     --cluster <cluster-name> \
     --attach-policy-arn arn:aws:iam::123456789012:policy/ACKBackupControllerPolicy \
     --approve
   ```

3. Install the controller with the service account annotation:

   ```bash
   helm install ack-backup-controller ack/backup-chart \
     --namespace ack-system \
     --set aws.region=us-west-2 \
     --set serviceAccount.create=false \
     --set serviceAccount.name=ack-backup-controller
   ```

## Troubleshooting IAM Issues

### Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `AccessDeniedException` | Missing IAM permissions | Add required permissions to the controller role |
| `InvalidParameterValueException: IAM Role ARN is invalid` | Invalid role ARN format | Verify the role ARN format and existence |
| `InvalidParameterValueException: The specified IAM role cannot be assumed` | Trust policy issue | Update the role's trust policy to allow `backup.amazonaws.com` |

### Debugging Steps

1. Check controller logs:
   ```bash
   kubectl logs -n ack-system deployment/ack-backup-controller
   ```

2. Verify IAM role permissions:
   ```bash
   aws iam simulate-principal-policy \
     --policy-source-arn arn:aws:iam::123456789012:role/ACKBackupControllerRole \
     --action-names backup:CreateBackupVault
   ```

3. Test role assumption:
   ```bash
   aws sts assume-role \
     --role-arn arn:aws:iam::123456789012:role/AWSBackupDefaultServiceRole \
     --role-session-name test
   ```
