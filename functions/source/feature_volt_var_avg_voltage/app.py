import json, os, time
from pyathena import connect
from statistics import mean

import boto3

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.batch import BatchProcessor, EventType, batch_processor
from aws_lambda_powertools.utilities.data_classes.sqs_event import SQSRecord
from aws_lambda_powertools.utilities.typing import LambdaContext

processor = BatchProcessor(event_type=EventType.SQS)
tracer = Tracer()
logger = Logger()

sqs_client = boto3.client('sqs')

queue_name = "volt_var_queue"
queue_name = os.environ['volt_var_calculation_queue']
queue_url = sqs_client.get_queue_url(QueueName=queue_name)["QueueUrl"]


@tracer.capture_method
def record_handler(record: SQSRecord):
    payload: str = record.body

    if payload:
        item: dict = json.loads(payload)

        region = os.environ['AWS_REGION']

        meter_cursor = connect(s3_staging_dir="s3://lambda-layer-data-4711/",
                               region_name=region).cursor()

        readings_cursor = connect(s3_staging_dir="s3://lambda-layer-data-4711/",
                                  region_name=region).cursor()

        voltages: list = []
        service_transformer_id = item["service_transformer_id"]
        reference_time = item["reference_time"]

        tic = time.perf_counter()
        meter_cursor.execute(
            "SELECT * FROM mda_database_integrated.topology_data_integrated_smart_meter WHERE servicetransformerid = %(param)s",
            {"param": service_transformer_id})
        toc = time.perf_counter()
        logger.info(f"Query 1 time in {toc - tic:0.4f} seconds")

        for meter in meter_cursor:
            tic = time.perf_counter()
            readings_cursor.execute("""SELECT * FROM mda_database_integrated.meter_readings_integrated_parquet 
                    WHERE reading_date_time between 
                        DATE_ADD('hour', -1, parse_datetime(%(reference_time)s,'yyyy-MM-dd HH:mm:ss.SSS')) AND parse_datetime(%(reference_time)s,'yyyy-MM-dd HH:mm:ss.SSS')
                    AND reading_type = 'vltg'
                    AND meter_id = %(meterid)s;
                """, {"reference_time": reference_time, "meterid": meter[0]})
            toc = time.perf_counter()
            logger.info(f"Query 2 time in {toc - tic:0.4f} seconds")

            for reading in readings_cursor:
                voltages.append(reading[1])

        mean_voltage_of_service_transformer = mean(voltages) * 1000

        # -> write to SQS {"serviceTransformerId": "ABCD-1234", "meanVoltage": 47.32}
        sqs_message = json.dumps(
            {"serviceTransformerId": service_transformer_id, "meanVoltage": mean_voltage_of_service_transformer})

        sqs_client.send_message(QueueUrl=queue_url, MessageBody=sqs_message)


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@batch_processor(record_handler=record_handler, processor=processor)
def lambda_handler(event, context: LambdaContext):
    return processor.response()
