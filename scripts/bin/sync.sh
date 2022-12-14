#!/usr/bin/env bash
cd ../..
aws s3 sync . s3://$1 --exclude "*" --include "scripts/assets/*" --include "functions/*" --include "templates/*" --include "submodules/*" --include "showcase/data/grid_topology/*" --region us-east-1
cd scripts