# ACK service controller for AWS Backup

This repository contains source code for the AWS Controllers for Kubernetes
(ACK) service controller for AWS Backup.

AWS Backup is a fully managed backup service that centralizes and automates
data protection across AWS services. This controller enables Kubernetes users
to manage AWS Backup resources declaratively using Kubernetes custom resources.

## Supported Resources

The controller supports the following AWS Backup resources:

| Resource | Description |
|----------|-------------|
| `BackupVault` | Logical containers for storing recovery points with encryption, access policies, and lock configuration |
| `BackupPlan` | Backup policies defining schedules, retention, and copy actions |
| `BackupSelection` | Resource assignments linking backup plans to AWS resources (e.g., DynamoDB tables) |

## Prerequisites

- Kubernetes cluster (v1.16+)
- Helm 3.x
- AWS credentials configured (via IRSA, instance profile, or secrets)
- IAM permissions for AWS Backup operations (see [IAM Permissions](#iam-permissions))

## Installation

### Using Helm

```bash
# Add the ACK Helm repository (if not already added)
helm repo add ack https://aws-controllers-k8s.github.io/community/helm

# Update the Helm repository
helm repo update

# Install the controller
helm install ack-backup-controller ack/backup-chart \
  --namespace ack-system \
  --create-namespace \
  --set aws.region=<your-aws-region>
```

### Configuration Options

Key configuration options in `values.yaml`:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `aws.region` | AWS region for API calls | `""` |
| `serviceAccount.annotations` | Annotations for the service account (use for IRSA) | `{}` |
| `installScope` | Installation scope (`cluster` or `namespace`) | `cluster` |
| `reconcile.defaultResyncPeriod` | Default resync period in seconds | `36000` |

For IRSA (IAM Roles for Service Accounts):

```bash
helm install ack-backup-controller ack/backup-chart \
  --namespace ack-system \
  --create-namespace \
  --set aws.region=us-west-2 \
  --set serviceAccount.annotations."eks\.amazonaws\.com/role-arn"=arn:aws:iam::123456789012:role/ACKBackupControllerRole
```

## Quick Start: DynamoDB Backup Example

This example demonstrates how to set up automated daily backups for DynamoDB tables.

### Step 1: Create a Backup Vault

```yaml
apiVersion: backup.services.k8s.aws/v1alpha1
kind: BackupVault
metadata:
  name: dynamodb-backup-vault
spec:
  backupVaultName: "dynamodb-backup-vault"
  tags:
    Environment: production
    ManagedBy: ACK
```

Apply the manifest:

```bash
kubectl apply -f backup-vault.yaml
```

### Step 2: Create a Backup Plan

```yaml
apiVersion: backup.services.k8s.aws/v1alpha1
kind: BackupPlan
metadata:
  name: daily-dynamodb-backup
spec:
  backupPlan:
    backupPlanName: "daily-dynamodb-backup"
    rules:
      - ruleName: "daily-backup-rule"
        targetBackupVaultName: "dynamodb-backup-vault"
        scheduleExpression: "cron(0 5 ? * * *)"  # Daily at 5:00 AM UTC
        startWindowMinutes: 60
        completionWindowMinutes: 180
        lifecycle:
          deleteAfterDays: 35  # Retain backups for 35 days
  tags:
    Environment: production
```

Apply the manifest:

```bash
kubectl apply -f backup-plan.yaml
```

### Step 3: Create a Backup Selection

First, ensure you have an IAM role for AWS Backup with the necessary permissions.
Then create a selection to specify which DynamoDB tables to back up:

```yaml
apiVersion: backup.services.k8s.aws/v1alpha1
kind: BackupSelection
metadata:
  name: dynamodb-tables-selection
spec:
  backupPlanID: "<backup-plan-id>"  # Get from BackupPlan status after creation
  backupSelection:
    selectionName: "dynamodb-tables"
    iamRoleARN: "arn:aws:iam::123456789012:role/AWSBackupDefaultServiceRole"
    # Option 1: Select specific tables by ARN
    resources:
      - "arn:aws:dynamodb:us-west-2:123456789012:table/users"
      - "arn:aws:dynamodb:us-west-2:123456789012:table/orders"
    # Option 2: Select tables by tag (uncomment to use)
    # listOfTags:
    #   - conditionType: "STRINGEQUALS"
    #     conditionKey: "backup"
    #     conditionValue: "true"
```

Get the backup plan ID from the status:

```bash
kubectl get backupplan daily-dynamodb-backup -o jsonpath='{.status.backupPlanID}'
```

Update the `backupPlanID` in the selection manifest and apply:

```bash
kubectl apply -f backup-selection.yaml
```

### Step 4: Verify Resources

```bash
# Check BackupVault status
kubectl get backupvault dynamodb-backup-vault

# Check BackupPlan status
kubectl get backupplan daily-dynamodb-backup

# Check BackupSelection status
kubectl get backupselection dynamodb-tables-selection

# View detailed status
kubectl describe backupvault dynamodb-backup-vault
```

## IAM Permissions

### Controller IAM Policy

The controller requires the following IAM permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "backup:CreateBackupVault",
        "backup:DeleteBackupVault",
        "backup:DescribeBackupVault",
        "backup:PutBackupVaultAccessPolicy",
        "backup:PutBackupVaultLockConfiguration",
        "backup:CreateBackupPlan",
        "backup:DeleteBackupPlan",
        "backup:GetBackupPlan",
        "backup:UpdateBackupPlan",
        "backup:CreateBackupSelection",
        "backup:DeleteBackupSelection",
        "backup:GetBackupSelection",
        "backup:TagResource",
        "backup:UntagResource",
        "backup:ListTags"
      ],
      "Resource": "*"
    }
  ]
}
```

### BackupSelection IAM Role

The IAM role specified in `BackupSelection.spec.backupSelection.iamRoleARN` must have:

1. Trust relationship allowing AWS Backup to assume the role
2. Permissions to back up the target resources

Example trust policy:

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

Example permissions for DynamoDB backups:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:CreateBackup",
        "dynamodb:DescribeTable",
        "dynamodb:ListTagsOfResource"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/*"
    },
    {
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

You can use the AWS managed policy `AWSBackupServiceRolePolicyForBackup` for common backup scenarios.

## Troubleshooting

### Common Issues

1. **Resource stuck in "Creating" state**: Check the controller logs and ensure IAM permissions are correct.

   ```bash
   kubectl logs -n ack-system deployment/ack-backup-controller
   ```

2. **Access Denied errors**: Verify the controller's IAM role has the required permissions.

3. **BackupSelection creation fails**: Ensure the `backupPlanID` is correct and the IAM role ARN is valid.

## Contributing

We welcome community contributions and pull requests.

See our [contribution guide](/CONTRIBUTING.md) for more information on how to
report issues, set up a development environment, and submit code.

We adhere to the [Amazon Open Source Code of Conduct][coc].

You can also learn more about our [Governance](/GOVERNANCE.md) structure.

[coc]: https://aws.github.io/code-of-conduct

## License

This project is [licensed](/LICENSE) under the Apache-2.0 License.

Please [log issues][ack-issues] and feedback on the main AWS Controllers for
Kubernetes Github project.

[ack-issues]: https://github.com/aws/aws-controllers-k8s/issues
