# Guidance for Meter Data Analytics on AWS

## Grafana usage
Before deploying the stack, please consult the [Grafana documentation](doc/grafana.md), if you want to use the dashboards.

## Deployment

With this instruction describes how to deploy the Meter Data Analytics (MDA) guidance to your own account.

### Prerequisite

- Docker

### 1. Copy the MDA data to your own S3 Bucket

The MDA artefacts have to be copied to an S3 bucket from which it will be deployed.
Before copying to S3, the sync script packages all AWS Lambda functions (Docker required).

1. Create an S3 Bucket in your account:
   `aws s3 mb s3://mda-data-<account_id>`

2. Use the `sync.sh` script to sync the needed artefacts to S3:
   ```bash
   cd scripts/bin
   ./sync.sh mda-data-<account_id>/artefacts us-east-1
   ```

### 2. Create configuration

The configuration parameter can be provided via the Console, CLI or File.
Here we use the provided script `apply-stack.sh` to deploy the Quick Start, the scripts expects the parameter json as an input value.

Adjust the following template and store it besides the `apply-stack.sh` as `stack-parameter.json`. 

```json
[
   {
      "ParameterKey":"QSS3BucketName",
      "ParameterValue":"mda-data-<account_id>"
   },
   {
      "ParameterKey":"QSS3KeyPrefix",
      "ParameterValue":"artefacts/"
   },
   {
      "ParameterKey":"QSS3BucketRegion",
      "ParameterValue":"us-east-1"
   },
   {
      "ParameterKey":"MeterDataGenerator",
      "ParameterValue":"ENABLED"
   },
   {
      "ParameterKey":"GenerationInterval",
      "ParameterValue":"15"
   },
   {
      "ParameterKey":"TotalDevices",
      "ParameterValue":"5000"
   }
]
```

### 3. Deploy the MDA

```bash
cd scripts/bin
./apply-stack.sh stack-parameter.json us-east-1
```

### 4. Delete the MDA stack

The delete script will empty all buckets before removing the stack.
```bash
cd scripts/bin
./delete-stack.sh
```

## CI Checks (Optional)
### Taskcat
Install and run [Taskcat](https://github.com/aws-ia/taskcat)

### CFN Lint
Install and run [CFN Lint](https://github.com/aws-cloudformation/cfn-lint) + [Custom RuleSet](https://github.com/aws-quickstart/qs-cfn-lint-rules)

`cfn-lint templates/**/*.yaml -a ../qs-cfn-lint-rules/qs_cfn_lint_rules/ > cfn-lint_output.txt`