#!/usr/bin/env bash

BUCKET=${1:?Please specify a destination bucket name}
REGION=${2:-us-east-1}

#echo "Packaging lambda functions first."
#./lambda-package.sh

echo "Sync to $1"
cd ../
aws s3 sync . s3://$BUCKET --exclude "*" --include "scripts/assets/*" --include "scripts/layers/*" --include "templates/*" --include "showcase/data/grid_topology/*" --include "assets/*" --region $REGION

cd scripts