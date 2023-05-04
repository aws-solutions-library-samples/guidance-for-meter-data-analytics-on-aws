#!/usr/bin/env bash

REGION=${1:-us-east-1}

aws logs describe-log-groups --query 'logGroups[*].logGroupName' --output table --region $REGION | \
awk '{print $2}' | \
grep ^/aws | \
while read x; do  echo "deleting $x" ; aws logs delete-log-group --log-group-name --region $REGION $x; done