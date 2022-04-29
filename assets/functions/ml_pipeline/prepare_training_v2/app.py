'''
Input event payload expected to be in the following format:

{
  "Data_start": "2013-06-01",
  "Data_end": "2014-01-01",
  "Forecast_period": 7,
  "Training_samples": 0.5
}

'''
#for later?
#import sys
#!{sys.executable} -m pip install PyAthena

import boto3, os, io
import json
import pandas as pd
import random

from pyathena import connect

REGION = os.environ['AWS_REGION']
ATHENA_OUTPUT_BUCKET = os.environ['Athena_bucket']
S3_BUCKET = os.environ['Working_bucket']
DB_SCHEMA = os.environ['Db_schema']
USE_WEATHER_DATA = os.environ['With_weather_data']

S3 = boto3.resource('s3')
ATHENA_CONNECTION = connect(s3_staging_dir='s3://{}/'.format(ATHENA_OUTPUT_BUCKET), region_name=REGION)

DYNAMODB = boto3.resource('dynamodb')

CONFIG_TABLE_NAME = os.environ['config_table']

def get_config(name):
    response = DYNAMODB.Table(CONFIG_TABLE_NAME).get_item(
        Key={'name': name}
    )

    return response['Item']["value"]

def get_weather(connection, start, schema):
    weather_data = '''select date_parse(time,'%Y-%m-%d %H:%i:%s') as datetime, 
    temperature, apparenttemperature,  humidity
    from "{}".weather
    where time >= '{}'
    order by 1;
    '''.format(schema, start)
    df_weather = pd.read_sql(weather_data, connection)
    df_weather = df_weather.set_index('datetime')
    return df_weather


def get_anomalous_data(connection, schema, meter_samples):
    anomalous_data = '''select meter_id, ds from "{}".anomaly where anomaly=1 and meter_id in ('{}');'''.format(schema, "','".join(meter_samples))
    df_anomalous_data = pd.read_sql(anomalous_data, connection)
    #print('df_anomalous_data:')
    #print(df_anomalous_data)
    return df_anomalous_data


# parameter training samples as proportion of data to be used (between 0 and 1)
def get_meter_ids(training_samples):
    meters = get_config('meter_ids')
    # get random subset of size training_samples * len(meters)
    meters_subset = random.sample(meters, int(training_samples * len(meters)))
    return meters_subset;

def write_upload_file(bucket, path, data):
    json_buffer = io.StringIO()
    for d in data:
        json_buffer.write(json.dumps(d))
        json_buffer.write('\n')

    S3.Bucket(bucket).Object(path).put(Body=json_buffer.getvalue())


def write_json_to_file(bucket, path, data):
    S3.Bucket(bucket).Object(path).put(Body=json.dumps(data))

# choose 1 year and 1 month as forecast period (data start to data end)
def lambda_handler(event, context):
    #training_samples = event['Training_samples'] # try out different sizes of training samples, start with all 
    training_samples = 0.05
    data_start = event['Data_start']
    data_end = event['Data_end']
    forecast_period = event['Forecast_period']
    prediction_length = forecast_period * 24

    meter_samples = get_meter_ids(training_samples)

    if training_samples == 1:
        q = '''
            select date_trunc('HOUR', reading_date_time) as datetime, meter_id, sum(reading_value) as consumption
                from "{}".daily
                where reading_type = 'INT'
                and reading_date_time >= timestamp '{}'
                and reading_date_time < timestamp '{}'
                group by 2, 1
        '''.format(DB_SCHEMA, data_start, data_end)
    else:
        q = '''
                select date_trunc('HOUR', reading_date_time) as datetime, meter_id, sum(reading_value) as consumption
                    from "{}".daily
                    where meter_id in ('{}')
                    and reading_type = 'INT'
                    and reading_date_time >= timestamp '{}'
                    and reading_date_time < timestamp '{}'
                    group by 2, 1
            '''.format(DB_SCHEMA, "','".join(meter_samples), data_start, data_end)
    
    result = pd.read_sql(q, ATHENA_CONNECTION)

    # fetch and prepare anomalies
    df_anomalies = get_anomalous_data(ATHENA_CONNECTION, DB_SCHEMA, meter_samples)
    df_anomalies['end_time'] = pd.to_datetime(df_anomalies['ds']) + pd.Timedelta(23,unit='H')
    df_anomalies['start_time'] = pd.to_datetime(df_anomalies['ds'])
    
    # filter out anomalies from training data
    for i in df_anomalies.index:
        result.loc[(result['datetime']>=df_anomalies.iloc[i]['start_time']) & (result['datetime']<=df_anomalies.iloc[i]['end_time']) & (result['meter_id']==df_anomalies.iloc[i]['meter_id']), 'consumption']= "NaN" #None

    # prepare timeseries
    result = result.set_index('datetime')

    timeseries = {}
    for meter_id in meter_samples:
        data_sorted = result[result['meter_id'] == meter_id].sort_values(by='datetime')
        data_sorted.drop('meter_id', axis=1, inplace=True)
        timeseries[meter_id] = data_sorted.iloc[:, 0]
        # previous code
        # do I still need resampling?
        # this code will add 0 instead of nan
        #data_kw = result[result['meter_id'] == meter_id].resample('1H').sum()  
        #timeseries[meter_id] = data_kw.iloc[:, 0]  # np.trim_zeros(data_kw.iloc[:,0], trim='f')

    # TODO:
    # start date is not always correct, adjust to actual time series start 


    freq = 'H'
    num_test_windows = 2
    start_dataset = pd.Timestamp(data_start, freq=freq)
    end_dataset = pd.Timestamp(data_end, freq=freq) - pd.Timedelta(1, unit='H')
    end_training = end_dataset - pd.Timedelta(prediction_length * num_test_windows, unit='H')


    if USE_WEATHER_DATA == 1:
        df_weather = get_weather(ATHENA_CONNECTION, data_start, DB_SCHEMA)

        training_data = [
            {
                "start": str(start_dataset),
                "target": ts[start_dataset:end_training].tolist(),
                # We use -1, because pandas indexing includes the upper bound
                "dynamic_feat": [df_weather['temperature'][
                                 start_dataset:start_dataset + pd.Timedelta(ts[start_dataset:end_training].size - 1,
                                                                            unit='H')].tolist(),
                                 df_weather['humidity'][
                                 start_dataset:start_dataset + pd.Timedelta(ts[start_dataset:end_training].size - 1,
                                                                            unit='H')].tolist(),
                                 df_weather['apparenttemperature'][
                                 start_dataset:start_dataset + pd.Timedelta(ts[start_dataset:end_training].size - 1,
                                                                            unit='H')].tolist()]
            }
            for meterid, ts in timeseries.items()
        ]

        # there could be missing data, so use actual timeseries size
        testing_data = [
            {
                "start": str(start_dataset),
                "target": ts[start_dataset:end_dataset].tolist(),
                "dynamic_feat": [df_weather['temperature'][
                                 start_dataset:start_dataset + pd.Timedelta(ts[start_dataset:end_dataset].size - 1,
                                                                            unit='H')].tolist(),
                                 df_weather['humidity'][
                                 start_dataset:start_dataset + pd.Timedelta(ts[start_dataset:end_dataset].size - 1,
                                                                            unit='H')].tolist(),
                                 df_weather['apparenttemperature'][
                                 start_dataset:start_dataset + pd.Timedelta(ts[start_dataset:end_dataset].size - 1,
                                                                            unit='H')].tolist()]
            }
            for k in range(1, num_test_windows + 1)
            for meterid, ts in timeseries.items()
        ]
    else:
        training_data = [
            {
                "start": str(start_dataset),
                "target": ts[start_dataset:end_training].tolist()
                # We use -1, because pandas indexing includes the upper bound
            }
            for meterid, ts in timeseries.items()
        ]
    
        testing_data = [
            {
                "start": str(start_dataset),
                "target": ts[start_dataset:end_dataset].tolist()
            }
            for k in range(1, num_test_windows + 1)
            for meterid, ts in timeseries.items()
        ]
    
    write_upload_file(S3_BUCKET, 'meteranalytics/train/training.json', training_data)
    write_upload_file(S3_BUCKET, 'meteranalytics/test/testing.json', testing_data)
