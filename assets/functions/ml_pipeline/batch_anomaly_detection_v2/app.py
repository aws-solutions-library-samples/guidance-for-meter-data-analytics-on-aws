import boto3, os
import pandas as pd

from pyathena import connect
from fbprophet import Prophet

REGION = os.environ['AWS_REGION']
ATHENA_OUTPUT_BUCKET = os.environ['Athena_bucket']
S3_BUCKET = os.environ['Working_bucket']
DB_SCHEMA = os.environ['Db_schema']
ATHENA_CONNECTION = connect(s3_staging_dir='s3://{}/'.format(ATHENA_OUTPUT_BUCKET), region_name=REGION)

S3 = boto3.resource('s3')

DYNAMODB = boto3.resource('dynamodb')

CONFIG_TABLE_NAME = os.environ['config_table']

def get_config(name):
    response = DYNAMODB.Table(CONFIG_TABLE_NAME).get_item(
        Key={'name': name}
    )

    return response['Item']["value"]


def weekend(ds):
    ds = pd.to_datetime(ds)

    if ds.weekday() > 4:
        return 1
    else:
        return 0


def get_batch_data(meter_start, meter_end, data_end, db_schema, connection):
    query = '''select meter_id, date_trunc('day', reading_date_time) as ds, sum(reading_value) as y 
  from "{}".daily
    where meter_id between '{}' and '{}'
    and reading_type = 'INT'
  and reading_date_time > date_add('year', -1, timestamp '{}')
  and reading_date_time <= timestamp '{}'
    group by 2,1
    order by 2,1;
    '''.format(db_schema, meter_start, meter_end, data_end, data_end)

    df_daily = pd.read_sql(query, connection)
    df_daily['weekend'] = df_daily['ds'].apply(weekend)
    return df_daily


def fit_predict_model(meter, timeseries):
    m = Prophet(daily_seasonality=False, yearly_seasonality=True, weekly_seasonality=True,
                seasonality_mode='multiplicative',
                interval_width=.98,
                changepoint_range=.8)
    m.add_country_holidays(country_name='UK')
    m.add_regressor('weekend')

    m = m.fit(timeseries)
    forecast = m.predict(timeseries)
    forecast['consumption'] = timeseries['y'].reset_index(drop=True)
    forecast['meter_id'] = meter

    forecast['anomaly'] = 0
    forecast.loc[forecast['consumption'] > forecast['yhat_upper'], 'anomaly'] = 1
    forecast.loc[forecast['consumption'] < forecast['yhat_lower'], 'anomaly'] = -1

    # anomaly importance
    forecast['importance'] = 0
    forecast.loc[forecast['anomaly'] == 1, 'importance'] = \
        (forecast['consumption'] - forecast['yhat_upper']) / forecast['consumption']
    forecast.loc[forecast['anomaly'] == -1, 'importance'] = \
        (forecast['yhat_lower'] - forecast['consumption']) / forecast['consumption']

    return forecast


def process_batch(meter_start, meter_end, data_end, db_schema, connection):
    query = '''select meter_id, max(ds) as ds from "{}".anomaly
               where meter_id between '{}' and '{}' group by 1;
        '''.format(db_schema, meter_start, meter_end)
    df_anomaly = pd.read_sql(query, connection)
    anomaly_meters = df_anomaly.meter_id.tolist()

    df_timeseries = get_batch_data(meter_start, meter_end, data_end, db_schema, connection)
    meters = df_timeseries.meter_id.unique()
    column_list = ['meter_id', 'ds', 'consumption', 'yhat_lower', 'yhat_upper', 'anomaly', 'importance'] #add yhat here
    df_result = pd.DataFrame(columns=column_list)
    for meter in meters:
        df_meter = df_timeseries[df_timeseries.meter_id == meter]
        # Run anomaly detection only if it's not done before or there are new data added
        if meter not in anomaly_meters:
            print("process anomaly for meter", meter)
            df_forecast = fit_predict_model(meter, df_meter)
            df_result = df_result.append(df_forecast[column_list], ignore_index=True)
        else:
            latest = pd.to_datetime(df_anomaly[df_anomaly.meter_id == meter]['ds'].iloc[0])
            if df_meter.ds.max() > latest:
                print("process anomaly for meter {} from {}".format(meter, latest))
                df_forecast = fit_predict_model(meter, df_meter)
                df_new_anomaly = df_forecast[df_forecast.ds > latest]
                df_result = df_result.append(df_new_anomaly[column_list], ignore_index=True)
            else:
                print("skip meter", meter)

    return df_result


def lambda_handler(event, context):
    batch_start = event['Batch_start']
    batch_end = event['Batch_end']
    #get 'Data_end' from DynamoDB
    data_end = get_config('Data_end') #why data end? why not just go to the end of the available readings? # because of the the s3 file name?
    # anomalies only calculated until data end
    # looks at the last year up until data end (like for 2014-01-01 consider readings since 201)

    result = process_batch(batch_start, batch_end, data_end, DB_SCHEMA, ATHENA_CONNECTION)

    result.to_csv('/tmp/anomaly.csv', index=False)
    S3.Bucket(S3_BUCKET) \
        .Object(os.path.join('meteranalytics', 'anomaly/{}/batch_{}_{}.csv'.format(data_end, batch_start, batch_end))) \
        .upload_file('/tmp/anomaly.csv')