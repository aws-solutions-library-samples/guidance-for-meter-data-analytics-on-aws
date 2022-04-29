import json
import os
import uuid
import boto3

import pandas as pd
from pyathena import connect

REGION = os.environ['AWS_REGION']
ATHENA_BUCKET = os.environ['Athena_bucket']
S3_BUCKET = os.environ['Working_bucket']
SCHEMA = os.environ['Db_schema']

ATHENA_CONNECTION = connect(s3_staging_dir='s3://{}/'.format(ATHENA_BUCKET), region_name=REGION)

DYNAMODB = boto3.resource('dynamodb')

CONFIG_TABLE_NAME = os.environ['config_table']

def get_config(name):
    response = DYNAMODB.Table(CONFIG_TABLE_NAME).get_item(
        Key={'name': name}
    )

    return response['Item']["value"]

def lambda_handler(event, context):
    
    #read list of distinct meter ids from DynamoDB
    meters = get_config('meter_ids')
    
    start = int(1-1); # should be 0 but didnt seem to work at first. # list index starts from 0
    end = len(meters) -1;
    batch_size = int(get_config('Batch_size'))
    #batch_size = event['Batch_size'] if 'Batch_size' in event else 25


    id = uuid.uuid4().hex #what is this used for?
    batchdetail = []

    # Cap the batch size to 100 so the lambda function doesn't timeout
    if batch_size > 100:
        batch_size = 100
        
    
    #for a in range(start, min(end+1, len(meters)), batch_size):
    for a in range(start, len(meters), batch_size):
        job = {}
        meter_start = meters[a]

        #upper_limit = min(end, a + batch_size - 1, len(meters)-1)
        upper_limit = min(a + batch_size - 1, len(meters)-1)

        meter_end = meters[upper_limit]
        
        job['Batch_start'] = meter_start
        job['Batch_end'] = meter_end
        batchdetail.append(job)
    

    return batchdetail