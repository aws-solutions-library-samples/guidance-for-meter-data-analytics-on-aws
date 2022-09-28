from meteostat import Hourly, Stations
from datetime import datetime, timedelta
import boto3
import logging
from botocore.exceptions import ClientError
import os

logging.getLogger().setLevel(logging.INFO)
s3 = boto3.client("s3")


def load_weather_data(start: datetime,
                      end: datetime):
    Stations.cache_dir = "/tmp/meteostat/stations"
    stations = Stations()
    stations = stations.nearby(47.608013, -122.335167)

    station = stations.fetch(1)

    Hourly.cache_dir = "/tmp/meteostat/hourly"
    data = Hourly(station, start, end)

    return data.fetch()


def lambda_handler(event, context):
    weather_data_bucket = os.environ["raw_data_bucket"]

    if "initial" in event and event["initial"] is True:
        logging.info("Running initial weather data load.")
        start = datetime(2015, 1, 1)
        end = datetime.today() - timedelta(days=1)
    else:
        logging.info("Running daily weather data load.")
        start = datetime.today() - timedelta(days=1)
        end = datetime.today()

    weather_data = load_weather_data(start, end)

    # write local file
    file_name = f"weather_data_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}.csv"
    weather_data.to_csv(f"/tmp/{file_name}", encoding='utf-8')
    # upload to S3
    try:
        s3.upload_file(f"/tmp/{file_name}", weather_data_bucket, f"weather/{file_name}")
    except ClientError as e:
        logging.error(e)

    return {
        "result": f"weather stored: {start.strftime('%Y-%m-%d')} - {end.strftime('%Y-%m-%d')} to weather/{file_name}",
        "statusCode": 200
    }
