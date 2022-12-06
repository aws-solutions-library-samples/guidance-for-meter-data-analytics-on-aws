import boto3
import logging
import os
from fastparquet import write
import pandas as pd
from botocore.exceptions import ClientError
import json

logging.getLogger().setLevel(logging.INFO)
s3 = boto3.client("s3")


def lambda_handler(event, context):
    topology_raw_data_bucket = os.environ["raw_data_bucket"]
    topology_integrated_data_bucket = os.environ["integrated_data_bucket"]

    logging.info(event)

    event_detail = event["detail"]
    objects = json.loads(event_detail["objects"])

    for object_key in objects:
        logging.info(f"Processing {object_key}")

        topology_content = s3.get_object(
            Bucket=topology_raw_data_bucket, Key=object_key)["Body"].read()

        json_topo = json.loads(topology_content.decode("utf-8"))

        new_file_name = object_key.replace(".json", ".parquet")
        df = pd.json_normalize(json_topo)

        os.makedirs(f"/tmp/{new_file_name}".rsplit('/', 1)[0], exist_ok=True) # nosec
        write(f"/tmp/{new_file_name}", df, compression='SNAPPY') # nosec

        try:
            s3.upload_file(f"/tmp/{new_file_name}", topology_integrated_data_bucket, f"{new_file_name}") # nosec
        except ClientError as e:
            logging.error(e)

    return {
        "result": f"",
        "statusCode": 200
    }
