# MIT No Attribution

# Copyright 2021 Amazon Web Services

# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import boto3
import json, time

import os
import logging
from datetime import datetime, timedelta, date
from pyathena import connect

from aws_lambda_powertools.utilities import parameters
from aws_lambda_powertools.utilities.typing import LambdaContext

logging.getLogger().setLevel(logging.INFO)

REGION = os.environ['AWS_REGION']

S3 = boto3.client('s3')
SAGEMAKER = boto3.client('runtime.sagemaker')


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    raise TypeError("Type %s not serializable" % type(obj))


def get_db():
    return os.environ['glue_integration_db_name']


def get_new_athena_cursor():
    region = os.environ['AWS_REGION']
    bucket = os.environ['bucket']
    return connect(s3_staging_dir=f"s3://{bucket}/athena/",
                   region_name=region).cursor()


def encode_request(consumption, start):
    instance = {
        "start": start,
        "target": consumption
    }

    configuration = {
        "num_samples": 50,
        "output_types": ["mean", "quantiles"],
        "quantiles": ["0.1", "0.5", "0.9"]
    }

    http_request_data = {
        "instances": [instance],
        "configuration": configuration
    }

    return json.dumps(http_request_data, default=json_serial).encode('utf-8')


def get_ssm_name():
    return os.environ['parameter_store_key_for_endpoint_name']


def get_endpoint_name():
    return parameters.get_parameter(get_ssm_name())


def decode_response(quantiles, prediction_time):
    prediction_length = len(quantiles)

    prediction_index = [prediction_time + timedelta(hours=x + 1) for x in range(prediction_length)]

    forecast = []
    for idx, q in enumerate(quantiles):
        forecast.append({
            "date_time": prediction_index[idx].strftime("%Y-%m-%d %H:%M:%S"),
            "consumption": q
        })

    return forecast


# /forecast/{meter_id}?forecast_start=yyyyMMddHHMMSS
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    logging.info(event)

    meter_id = event["pathParameters"]["meter_id"]

    if "queryStringParameters" not in event:
        return {
            'statusCode': 500,
            'body': "error: 'forecast_start' need to be provided as query parameter."
        }

    query_parameter = event["queryStringParameters"]

    if "forecast_start" not in query_parameter:
        return {
            'statusCode': 500,
            'body': "error: 'forecast_start' need to be provided as query parameter."
        }

    forecast_start = datetime.strptime(query_parameter["forecast_start"], '%Y%m%d%H%M%S')
    prediction_period_days = 3
    start = forecast_start - timedelta(days=prediction_period_days)
    ml_endpoint_name = get_endpoint_name()

    cursor = get_new_athena_cursor()
    tic = time.perf_counter()
    cursor.execute(
        f"""select date_trunc('HOUR', reading_date_time) as reading_date_time, sum(reading_value) as consumption
                FROM {get_db()}.meter_readings_integrated_parquet WHERE
                meter_id=%(meter_id)s AND
                reading_type='kw' AND 
                reading_date_time BETWEEN
                 parse_datetime(%(from)s,'YYYYMMddHHmmss') AND parse_datetime(%(to)s,'YYYYMMddHHmmss')
                group by 1
                order by 1
    """, {"meter_id": meter_id, "from": start.strftime("%Y%m%d%H%M%S"), "to": forecast_start.strftime("%Y%m%d%H%M%S")})
    toc = time.perf_counter()
    logging.info(f"Consumption query time in {toc - tic:0.4f} seconds")

    consumption = []
    for row in cursor:
        consumption.append(row[1])

    response = SAGEMAKER.invoke_endpoint(EndpointName=ml_endpoint_name,
                                         ContentType='application/json',
                                         Body=encode_request(consumption, start))

    b = (response['Body'].read()).decode('utf-8')
    predictions = json.loads(b)['predictions'][0]
    quantiles = predictions['quantiles']['0.9']

    forecast = decode_response(quantiles, forecast_start)

    return {
        "statusCode": 200,
        "headers": {
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET",
            "Content-Type": "application/json"
        },
        "body": json.dumps(forecast, default=json_serial)
    }
