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


def get_anomaly_db():
    return os.environ['glue_ml_feature_db_name']


def get_new_athena_cursor():
    region = os.environ['AWS_REGION']
    bucket = os.environ['bucket']
    return connect(s3_staging_dir=f"s3://{bucket}/athena/",
                   region_name=region).cursor()


# /anomaly/{meter_id}?year=2023
def lambda_handler(event, context):
    logging.info(event)

    meter_id = event["pathParameters"]["meter_id"]

    if "queryStringParameters" not in event:
        return {
            'statusCode': 500,
            'body': "error: 'year' need to be provided as query parameter."
        }

    query_parameter = event["queryStringParameters"]

    if "year" not in query_parameter:
        return {
            'statusCode': 500,
            'body': "error: 'year' need to be provided as query parameter."
        }

    year = query_parameter["year"]

    cursor = get_new_athena_cursor()
    tic = time.perf_counter()
    cursor.execute(
        f"""select * from {get_anomaly_db()}.meter_anomaly_results 
                where meter_id = %(meter_id)s and anomaly = -1 and year(cast(ds as date)) = %(y)d
    """, {"meter_id": meter_id, "y": int(year)})
    toc = time.perf_counter()
    logging.info(f"Anomaly query time in {toc - tic:0.4f} seconds")

    data = []
    for row in cursor:
        data.append({
            "anomaly_date": row[0],
            "meter_id": row[1],
            "consumption": row[2],
            "anomaly_importance": row[7]
        })

    return dumps(data, default=json_serial)
