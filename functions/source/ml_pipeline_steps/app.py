import json
import boto3
import os

STACK_NAME = os.environ['STACK_NAME']

ssm = boto3.client('ssm')
ParameterPrefix = '/mlpipeline/'+STACK_NAME+'/Steps/'


def get_config(name):
    
    parameter = ssm.get_parameter(Name=ParameterPrefix+name)
    return parameter['Parameter']['Value']


def write_config(name, value):
    response = ssm.put_parameter(Name=ParameterPrefix+name,
            Value=value,
            Type='String',
            Overwrite=True)

def lambda_handler(event, context):
    
    # check the value of 'inference', 'training' and 'anomaly' 
    # boolean values
    
    try: 
        anomaly = get_config('Anomaly')
        if anomaly=='FALSE':
            anomaly=False
        if anomaly=='TRUE':
            anomaly=True
    except ssm.exceptions.ParameterNotFound:
        write_config('Anomaly', 'FALSE')
        anomaly = False
    try:   
        training = get_config('Training')
        if training=='FALSE':
            training=False
        if training=='TRUE':
            training=True
    except ssm.exceptions.ParameterNotFound:
        write_config('Training', 'FALSE')
        training = False
        
    try:
        inference = get_config('Inference')
        if inference=='FALSE':
            inference=False
        if inference=='TRUE':
            inference=True
    except ssm.exceptions.ParameterNotFound:
        write_config('Inference', 'FALSE')
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
