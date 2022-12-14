## Utility Meter Data Analytics on the AWS Cloud—Quick Start

For architectural details, step-by-step instructions, and customization options, see the [deployment guide](https://aws-quickstart.github.io/quickstart-aws-utility-meter-data-analytics-platform/).

To post feedback, submit feature ideas, or report bugs, use the **Issues** section of this GitHub repo. 

To submit code for this Quick Start, see the [AWS Quick Start Contributor's Kit](https://aws-quickstart.github.io/).


## Customized deployment

With this instruction you will be able to deploy a customized built of the quickstart to your own account.

### Clone submodules
```bash
cd submodules
git submodule init 
git submodule update
cd -
```

### Package Lambda functions

If functions were adjusted the functions have to be packaged first.
To package the Lambda functions run the following script:

```bash
cd scripts/bin
./create_deployment_packages.sh
cd -
```

### Copy the MDA to your own S3 Bucket

The updated content have to be copied to an S3 bucket from which it will be deployed.

1. create an S3 Bucket in your account
   `aws s3 mb s3://mda-data-<account_id>`
2. use the `sync.sh` script to sync the needed artefacts to S3
   ```bash
   cd scripts/bin
   ./sync.sh mda-data-<account_id>/artefacts
   ```

### Create configuration

The configuration parameter can be provided via the Console, CLI or File.
Here we use the provided script `apply-stack.sh` to deploy the Quick Start, the scripts expects the parameter json as an input value.

Adjust the following template and store it besides the `apply-script.sh` as `stack-parameter.json`. (will create a new VPC)

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
      "ParameterValue":"5"
   },
   {
      "ParameterKey":"TotalDevices",
      "ParameterValue":"5000000"
   }
]
```

### Deploy MDA

Call the apply script and provide the stack parameter file:
```bash
cd scripts/bin
./apply-stack.sh stack-parameter.json
```

### Delete the MDA stack

The delete script will empty all buckets before removing the stack
```bash
cd scripts/bin
./delete-stack.sh
```
