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


def get_integrated_db():
    return os.environ['glue_integration_db_name']


def get_queue_url():
    queue_name = os.environ['volt_var_calculation_queue']
    return sqs_client.get_queue_url(QueueName=queue_name)["QueueUrl"]


def get_new_athena_cursor():
    region = os.environ['AWS_REGION']
    bucket = os.environ['volt_var_bucket']
    return connect(s3_staging_dir=f"s3://{bucket}/athena/",
                   region_name=region).cursor()


@tracer.capture_method
def record_handler(record: SQSRecord):
    payload: str = record.body

    if payload:
        item: dict = json.loads(payload)

        avg_vltg_cursor = get_new_athena_cursor()

        distribution_transformer_id = item["distribution_transformer_id"]
        reference_time = item["reference_time"]

        tic = time.perf_counter()
        avg_vltg_cursor.execute(
            f"""SELECT avg(reading_value) FROM {get_integrated_db()}.meter_readings_integrated_parquet 
                    WHERE reading_date_time between 
                        DATE_ADD('hours', -1, parse_datetime(%(reference_time)s,'yyyy-MM-dd HH:mm:ss.SSS')) AND parse_datetime(%(reference_time)s,'yyyy-MM-dd HH:mm:ss.SSS')
                    AND reading_type = 'vltg'
                    AND meter_id in (
                        SELECT meter.id FROM {get_integrated_db()}.topology_data_integrated_smart_meter as meter, {get_integrated_db()}.topology_data_integrated_service_transformer as st 
                            WHERE st.distributionTransformerId =  %(param)s AND meter.serviceTransformerId = st.id
                    )
                    group by reading_type""",
            {"param": distribution_transformer_id, "reference_time": reference_time})
        toc = time.perf_counter()
        logger.debug(f"Query 1 time in {toc - tic:0.4f} seconds")

        avg_vltg = avg_vltg_cursor.fetchone()
        if avg_vltg is not None:
            mean_voltage_of_distribution_transformer = avg_vltg[0] * 1000

            sqs_message = json.dumps(
                {"distribution_transformer_id": distribution_transformer_id,
                 "mean_voltage": mean_voltage_of_distribution_transformer})

            sqs_client.send_message(QueueUrl=get_queue_url(), MessageBody=sqs_message)


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@batch_processor(record_handler=record_handler, processor=processor)
def lambda_handler(event, context: LambdaContext):
    logger.info(event)
    return processor.response()
