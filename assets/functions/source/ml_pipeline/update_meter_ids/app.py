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

def lambda_handler(event, context):

    # Todo, more efficient way is to create a meter list table instead of getting it from raw data
    df_meters = pd.read_sql('''select distinct meter_id from "{}".daily order by meter_id'''.format(SCHEMA),
                            ATHENA_CONNECTION)
    meters = df_meters['meter_id'].tolist()
    
    DYNAMODB.Table(CONFIG_TABLE_NAME).put_item(
        Item={"name": "meter_ids", "value": meters}
    )


    return { **event }