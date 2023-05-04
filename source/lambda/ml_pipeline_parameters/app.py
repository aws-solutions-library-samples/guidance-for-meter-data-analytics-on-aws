import boto3
import os
import uuid
import datetime

STACK_NAME = os.environ['STACK_NAME']

ssm = boto3.client('ssm')
ParameterPrefixSteps = '/mlpipeline/'+STACK_NAME+'/Steps/'
ParameterPrefixForecast = '/mlpipeline/'+STACK_NAME+'/Forecast/'

S3_BUCKET = os.environ['S3_BUCKET_NAME']

def get_config(name):
    
    parameter = ssm.get_parameter(Name=ParameterPrefixForecast+name)
    return parameter['Parameter']['Value']


def write_config(name, value):
    response = ssm.put_parameter(Name=ParameterPrefixForecast+name,
            Value=value,
            Type='String',
            Overwrite=True)


def lambda_handler(event, context):

    current_datetime = datetime.datetime.now().isoformat()
    current_datetime = current_datetime.replace(':','-').replace('.','-')

    # if training workflow to be run, this runs in ML orchestrator workflow
    if 'training' in event:
        train_model = event['training']
    else:
        train_model = False

    if train_model:

        model_name = "model-{}".format(current_datetime) 
        job_name = "training-job-{}".format(current_datetime) 

        write_config("ModelName", model_name)
        write_config("TrainingJobName", job_name)

    else:
        model_name = get_config("ModelName")
        job_name = get_config("TrainingJobName")
    
    target_s3_bucket = S3_BUCKET
    target_s3_path = 'training/'+current_datetime
    train_s3_uri = f's3://{target_s3_bucket}/{target_s3_path}/train_data_parquet'
    test_s3_uri = f's3://{target_s3_bucket}/{target_s3_path}/test_data_parquet'

    
    # inference flow
    batchtransform_output_bucket = S3_BUCKET 
    batchtransform_output_path = 'inference/output/'+current_datetime
    batchtransform_output_s3_uri = f's3://{batchtransform_output_bucket}/{batchtransform_output_path}'
    
    batchtransform_input_bucket = S3_BUCKET 
    batchtransform_input_path = 'inference/input/'+current_datetime
    batchtransform_input_s3_uri = f's3://{batchtransform_input_bucket}/{batchtransform_input_path}'

    batchtransform_util_s3_uri = f's3://{batchtransform_input_bucket}/inference/util/{current_datetime}'

    parameter = {
        "Forecast_period": get_config("ForecastPeriod"), #str not int 
        "Prediction_length": str(int(get_config("ForecastPeriod"))*24),
        "Training_time_frame": get_config("TrainingTimeFrame"), #str
        "Training_instance_type": get_config("TrainingInstanceType"),
        "Endpoint_instance_type": get_config("EndpointInstanceType"),
        "ML_endpoint_name": get_config("EndpointName"),
        "ModelName": model_name,
        "Training_job_name": job_name,
        "Target_S3_bucket": target_s3_bucket,
        "Target_S3_path": target_s3_path,
        "Train_S3_uri": train_s3_uri,
        "Test_S3_uri": test_s3_uri,
        "Transform_instance_type": get_config("TransformInstanceType"),
        "BatchTransform_input_s3_uri": batchtransform_input_s3_uri,
        "BatchTransform_util_s3_uri": batchtransform_util_s3_uri,
        "BatchTransform_output_s3_uri": batchtransform_output_s3_uri,
        "BatchTransform_job_name": f'transform-job-{current_datetime}',
        "Timestamp": current_datetime,
        "Use_weather": ssm.get_parameter(Name='/mlpipeline/'+STACK_NAME+'/ML/UseWeather')['Parameter']['Value']
    }
    # add prediction length of forecast_period*24 (to have value in H instead of days)

    return {
        **parameter,
        **event
    }
