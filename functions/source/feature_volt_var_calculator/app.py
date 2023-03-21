import json
import boto3
import os
import logging
from time import time

dynamodb = boto3.resource('dynamodb')

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def write_records(item, table_name):
    table = dynamodb.Table(table_name)
    try:
        table.put_item(
            Item=item
        )
    except Exception as err:
        logging.error(err)


def lambda_handler(event, context):
    logging.info(event)

    dynamo_table = os.getenv("DYNAMO_TABLE")

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

    for record in event['Records']:
        payload = json.loads(record["body"])

        device_id = payload["serviceTransformerId"]
        mean_voltage = payload["meanVoltage"]

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
            'pct_voltage_reduction': pct_volt_red,
            'pct_energy_savings': pct_energy_savings,
            'actual_energy_savings': actual_energy_savings,
            'cost_avoided': cost_avoided,
            'cust_dollar_savings': cust_dollar_savings,
            'carbon_reduction_lbs': carbon_reduction_lbs
        }
        logging.info(item)

        write_records(item, dynamo_table)

    return {
        'statusCode': 200,
    }
