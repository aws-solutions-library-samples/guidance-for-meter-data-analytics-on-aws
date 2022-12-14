import json
import boto3
import os
import uuid

S3 = boto3.client('s3')
DYNAMODB = boto3.resource('dynamodb')

CONFIG_TABLE_NAME = os.environ['config_table']


def get_config(name):
    response = DYNAMODB.Table(CONFIG_TABLE_NAME).get_item(
        Key={'name': name}
    )

    return response['Item']["value"]


def write_config(name, value):
    DYNAMODB.Table(CONFIG_TABLE_NAME).put_item(
        Item={"name": name, "value": value}
    )

def lambda_handler(event, context):
    
    # check the value of 'inference', 'training' and 'anomaly' in DynamoDB
    # boolean values
    
    try: 
        anomaly = get_config('anomaly')
    except KeyError:
        write_config('anomaly', False)
        anomaly = False
    
    try:   
        training = get_config('training')
    except KeyError:
        write_config('training', False)
        training = False
        
    try:
        inference = get_config('inference')
    except KeyError:
        write_config('inference', False)
        inference = False
    
    parameter = {
        "training": training,
        "inference": inference,
        "anomaly": anomaly
    }
    
    return {
        **parameter,
        **event
    }
