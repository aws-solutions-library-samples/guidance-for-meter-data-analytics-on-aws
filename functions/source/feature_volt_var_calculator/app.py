import json
import boto3
import os
from datetime import datetime, timedelta
from botocore.config import Config
import time
from calendar import timegm
import random
from decimal import Decimal

#timestream_write = boto3.client('timestream-write')
#write_client = session.client('timestream-write', config=Config(read_timeout=20, max_pool_connections=5000,
#                                                                        retries={'max_attempts': 10}))

session = boto3.Session()
write_client = session.client('timestream-write', config=Config(
    read_timeout=20, max_pool_connections=5000, retries={'max_attempts': 10}))

def write_records(records, common_attributes):

    DATABASE_NAME="VVOData"
    TABLE_NAME="savingsCalc"

    try:
        result = write_client.write_records(DatabaseName=DATABASE_NAME,
                                            TableName=TABLE_NAME,
                                            CommonAttributes=common_attributes,
                                            Records=records)
        status = result['ResponseMetadata']['HTTPStatusCode']
        print("Processed %d records. WriteRecords HTTPStatusCode: %s" %
              (len(records), status))
    except Exception as err:
        print("Error:", err)


def prepare_measure(measure_name, measure_value):
    measure = {
        'Name': measure_name,
        'Value': str(measure_value),
        'Type': 'DOUBLE'
    }
    return measure

def lambda_handler(event, context):

    print(event)

    try:
        ## Code here
        print(f"Savings Calculator Module Initiated!")

        #======================================================================================================
        # Get event details (current sim time) from eventbridge
        #======================================================================================================
        current_DT = datetime.now()
        #current_DT = datetime.strptime("2020-07-08T03:05:00Z", "%Y-%m-%dT%H:%M:%SZ")
        print(f"Current DT: {current_DT}")

        #current_epoch = int(current_DT.timestamp()) ## this will be used to mark the timestamp for current RFC if controller failure is detected


        #======================================================================================================
        # Get boto3 clients
        #======================================================================================================
        dynamodb = boto3.resource('dynamodb', endpoint_url="https://dynamodb.us-east-1.amazonaws.com")
        session = boto3.Session()




        #======================================================================================================
        # Global variables for this lambda
        #======================================================================================================
        countNoResponse = 0
        savingsRecords = []
        epoch_ts = 0
        device_ID = None
        default_set_point = 220.0 # TODO float(os.environ['default_set_point'])

        # average V per distribution trans (avg feeder voltage)
        # 120 = default set point (depends on country) (avg from simulator)
        # between 3 or 4 volts

        #set_point_read = default_set_point
        pct_volt_red = 0
        cvr = 0.2 # TODO float(os.environ['cvr'])
        pct_energy_savings = 0
        actual_energy_savings = 0
        energy_purchase_price = 0.1 # TODO float(os.environ['energy_purchase_cents'])
        cost_avoided = 0
        electricity_rate = 0.1 # TODO float(os.environ['electricity_rate'])
        cust_dollar_savings = 0
        num_cust = 1 #TODO int(os.environ['num_cust'])
        carbon_savings_per_mwh = 5.0 # TODO float(os.environ['carbon_savings_per_mwh'])
        carbon_reduction_lbs = 0
        mu = 0
        sigma = 0.3

        #======================================================================================================
        # Get total energy consumption config for required hour
        #======================================================================================================

        relevant_DT = current_DT - timedelta(minutes=5)
        hour = relevant_DT.hour
        relevant_epoch = int(relevant_DT.timestamp())

        # TODO
        ## get total energy consumption from Dynamo
        # mw_table = dynamodb.Table(os.environ['SubstationMWProfile'])
        # mwLevelDictFromDynamo = mw_table.get_item(Key={'hour': hour}, ReturnConsumedCapacity='TOTAL')
        # mwLevel = float(mwLevelDictFromDynamo['Item']['mw'])
        # print(f"From dynamo, MW level is: {mwLevel}")
        # mwLevel = round((mwLevel + random.normalvariate(mu, sigma)),9)
        mwLevel = 1
        #======================================================================================================
        # Read latest SCADA data from SQS; Figure out if we have a controller failure
        #======================================================================================================

        for record in event['Records']:
            payload = json.loads(record["body"])


            deviceID = payload["serviceTransformerId"]
            mean_voltage = payload["meanVoltage"]


            # relevant_DT = relevant_DT + timedelta(minutes=5)
            # hour = relevant_DT.hour
            # relevant_epoch = relevant_epoch + 300
            # mwLevelDictFromDynamo = mw_table.get_item(Key={'hour': hour}, ReturnConsumedCapacity='TOTAL')
            # mwLevel = float(mwLevelDictFromDynamo['Item']['mw'])
            # print(f"From dynamo, MW level is: {mwLevel}")
            # mwLevel = round((mwLevel + random.normalvariate(mu, sigma)),9)
            # savingsRecords = []

            sp = 0 #set point
            dv = 0 #device volts
            device_ID = deviceID
            common_attributes = []
            pct_volt_timestream = {}
            pct_energy_timestream = {}
            energy_timestream = {}
            cost_avoided_timestream = {}
            cust_cost_saved_timestream = {}
            carbon_timestream = {}


            result_records = []
            common_attributes = {
                'Dimensions': [
                    {'Name': 'Device_ID', 'Value': deviceID},
                    {'Name': 'Device_Type', 'Value': 'Service Transformer'}
                ],
                'MeasureName': 'voltvar',
                'MeasureValueType': 'MULTI'
            }

            result_record = {
                'Time': str(relevant_epoch),
                'TimeUnit': 'SECONDS',
                'MeasureValues': []
            }

            #pct_volt_timestream['Dimensions'] = common_attributes
            #pct_energy_timestream['Dimensions'] = common_attributes
            #energy_timestream['Dimensions'] = common_attributes
            #cost_avoided_timestream['Dimensions'] = common_attributes
            #cust_cost_saved_timestream['Dimensions'] = common_attributes
            #carbon_timestream['Dimensions'] = common_attributes
            # average voltage of the feeder by comparing all V from the meter group

            #print(f"{deviceID} = {mean_voltage}")

            set_point_read = float(mean_voltage)
            pct_volt_red = round((default_set_point - set_point_read)*100/(default_set_point*12),9)
            result_record['MeasureValues'].append(prepare_measure('pct_voltage_reduction', pct_volt_red))
            print(f"Pct V Red: {pct_volt_red}")

            pct_energy_savings = round(pct_volt_red * cvr,9)
            result_record['MeasureValues'].append(prepare_measure('pct_energy_savings', pct_energy_savings))
            print(f"Pct Energy Savings: {pct_energy_savings}")

            actual_energy_savings = round(pct_energy_savings*mwLevel/1200,9)
            result_record['MeasureValues'].append(prepare_measure('actual_energy_savings', actual_energy_savings))
            print(f"Actual MW saved: {actual_energy_savings}")

            cost_avoided = round(energy_purchase_price*actual_energy_savings*1000/12,9)
            result_record['MeasureValues'].append(prepare_measure('cost_avoided', cost_avoided))
            print(f"Cents avoided in energy purchase: {cost_avoided}")

            cust_dollar_savings = round(electricity_rate*actual_energy_savings*1000/(12*num_cust),9)
            result_record['MeasureValues'].append(prepare_measure('cust_dollar_savings', cust_dollar_savings))
            print(f"Customer bill reduction in cents: {cust_dollar_savings}")

            carbon_reduction_lbs = round((carbon_savings_per_mwh*actual_energy_savings/12),9)
            result_record['MeasureValues'].append(prepare_measure('carbon_reduction_lbs', carbon_reduction_lbs))
            print(f"Carbon reduction in pounds: {carbon_reduction_lbs}")

            result_records.append(result_record)

            #savingsRecords.append(pct_volt_timestream)
            #savingsRecords.append(pct_energy_timestream)
            #savingsRecords.append(energy_timestream)
            #savingsRecords.append(cost_avoided_timestream)
            #savingsRecords.append(cust_cost_saved_timestream)
            #savingsRecords.append(carbon_timestream)

            #result = write_client.write_records(DatabaseName="VVOData", TableName="savingsCalc", Records=result_record, CommonAttributes=common_attributes)
            #print("WriteRecords Status: [%s]" % result['ResponseMetadata']['HTTPStatusCode'])
            write_records(result_records, common_attributes)



    #======================================================================================================
    # ## Save device data to Timestream
    #======================================================================================================

    # if len(savingsRecords) > 0:
    #     result = write_client.write_records(DatabaseName="VVOData", TableName="savingsCalc", Records=savingsRecords, CommonAttributes={})
    #     print("WriteRecords Status: [%s]" % result['ResponseMetadata']['HTTPStatusCode'])



    except Exception as e:
        print(str(e))


    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }
