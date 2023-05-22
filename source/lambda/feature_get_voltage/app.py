import os, time, logging
from pyathena import connect
from datetime import date, datetime
from json import dumps

logging.getLogger().setLevel(logging.INFO)


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))


def get_integrated_db():
    return os.environ['glue_integration_db_name']


def get_new_athena_cursor():
    region = os.environ['AWS_REGION']
    bucket = os.environ['bucket']
    return connect(s3_staging_dir=f"s3://{bucket}/athena/",
                   region_name=region).cursor()


# /voltage/{meter_id}?reading_date_from=20230101&reading_date_to=20230131
def lambda_handler(event, context):
    logging.info(event)

    meter_id = event["pathParameters"]["meter_id"]

    if "queryStringParameters" not in event:
        return {
            'statusCode': 500,
            'body': "error: 'reading_date_from' and 'reading_date_to' need to be provided as query parameter."
        }

    query_parameter = event["queryStringParameters"]

    if ("reading_date_from" not in query_parameter or "reading_date_to" not in query_parameter):
        return {
            'statusCode': 500,
            'body': "error: 'reading_date_from' and 'reading_date_to' need to be provided as query parameter."
        }

    reading_date_from = query_parameter["reading_date_from"]
    reading_date_to = query_parameter["reading_date_to"]

    cursor = get_new_athena_cursor()
    tic = time.perf_counter()
    cursor.execute(
        f"""SELECT * FROM {get_integrated_db()}.meter_readings_integrated_parquet 
            WHERE meter_id=%(meter_id)s
            AND reading_type='vltg'
            AND reading_date_time BETWEEN
                 parse_datetime(%(from)s,'yyyyMMdd') AND parse_datetime(%(to)s,'yyyyMMdd')
    """, {"meter_id": meter_id, "from": reading_date_from, "to": reading_date_to})
    toc = time.perf_counter()
    logging.info(f"Voltage query time in {toc - tic:0.4f} seconds")

    data = []
    for row in cursor:
        data.append({
            "meter_id": row[0],
            "reading_value": row[1],
            "reading_date_time": row[2],
            "reading_type": row[7]

        })

    return dumps(data, default=json_serial)
