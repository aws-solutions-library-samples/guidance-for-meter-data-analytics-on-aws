#!/usr/bin/env bash

set -e

PARAMETER_FILE=${1:?parameter file name is not set}
REGION=${2:-us-east-1}
STACK_NAME=meter-data-analytics

echo "Checking if stack exists ..."

if ! aws cloudformation describe-stacks --region $REGION --stack-name $STACK_NAME &>/dev/null ; then

  echo -e "\nStack does not exist, creating ..."
  aws cloudformation create-stack --stack-name $STACK_NAME \
                                --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND CAPABILITY_NAMED_IAM \
                                --template-body file://../templates/work-load.template.yaml \
                                --parameters file://$PARAMETER_FILE \
                                --region $REGION

  echo "Waiting for stack to be created ..."
  aws cloudformation wait stack-create-complete --stack-name $STACK_NAME --region $REGION

else

  echo -e "\nStack exists, attempting update ..."

  set +e
  update_output=$(
  aws cloudformation update-stack --stack-name $STACK_NAME \
                                --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND CAPABILITY_NAMED_IAM \
                                --template-body file://../templates/work-load.template.yaml \
                                --parameters file://$PARAMETER_FILE \
                                --region $REGION \
                                2>&1)
  status=$?
  set -e

  echo "$update_output"

  if [ $status -ne 0 ] ; then

    # Don't fail for no-op update
    if [[ $update_output == *"ValidationError"* && $update_output == *"No updates"* ]] ; then
      echo -e "\nFinished create/update - no updates to be performed"
      exit 0
    else
      exit $status
    fi

  fi

  echo "Waiting for stack update to complete ..."
  aws cloudformation wait stack-update-complete --stack-name $STACK_NAME --region $REGION

fi

echo "Finished create/update successfully!"