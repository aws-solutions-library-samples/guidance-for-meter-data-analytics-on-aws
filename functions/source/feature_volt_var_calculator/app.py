import json
import boto3
import os
from time import time
from decimal import Decimal

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.batch import BatchProcessor, EventType, batch_processor
from aws_lambda_powertools.utilities.data_classes.sqs_event import SQSRecord
from aws_lambda_powertools.utilities.typing import LambdaContext

processor = BatchProcessor(event_type=EventType.SQS)
tracer = Tracer()
logger = Logger()

dynamodb = boto3.resource('dynamodb')


def get_table_name():
    return os.getenv("DYNAMO_TABLE")


def write_records(item):
    table = dynamodb.Table(get_table_name())
    try:
        table.put_item(
            Item=item
        )
    except Exception as err:
        logger.error(err)


@tracer.capture_method
def record_handler(record: SQSRecord):
    payload: str = record.body

    if payload:
        item: dict = json.loads(payload)

        milliseconds = int(time() * 1000)

        default_set_point = 220.0  # TODO externalize

        # average V per distribution trans (avg feeder voltage)
        # 120 = default set point (depends on country) (avg from simulator)
        # between 3 or 4 volts

        cvr = 0.8  # TODO externalize
        energy_purchase_price = 0.11  # TODO externalize
        electricity_rate = 11  # TODO externalize
        num_cust = 1000  # TODO externalize
        carbon_savings_per_mwh = 900.0  # TODO externalize

        mw_level = 1

        device_id = item["distribution_transformer_id"]
        mean_voltage = item["mean_voltage"]

        set_point_read = float(mean_voltage)
        pct_volt_red = round((default_set_point - set_point_read) * 100 / (default_set_point * 12), 9)
        pct_energy_savings = round(pct_volt_red * cvr, 9)
        actual_energy_savings = round(pct_energy_savings * mw_level / 1200, 9)
        cost_avoided = round(energy_purchase_price * actual_energy_savings * 1000 / 12, 9)
        cust_dollar_savings = round(electricity_rate * actual_energy_savings * 1000 / (12 * num_cust), 9)
        carbon_reduction_lbs = round((carbon_savings_per_mwh * actual_energy_savings / 12), 9)

        item = {
            'id': f'{device_id}_{milliseconds}',
            'device_id': device_id,
            'pct_voltage_reduction': Decimal(str(pct_volt_red)),
            'pct_energy_savings': Decimal(str(pct_energy_savings)),
            'actual_energy_savings': Decimal(str(actual_energy_savings)),
            'cost_avoided': Decimal(str(cost_avoided)),
            'cust_dollar_savings': Decimal(str(cust_dollar_savings)),
            'carbon_reduction_lbs': Decimal(str(carbon_reduction_lbs))
        }
        logger.debug(item)

        write_records(item)


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@batch_processor(record_handler=record_handler, processor=processor)
def lambda_handler(event, context: LambdaContext):
    logger.info(event)
    return processor.response()
