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
    topology_staging_data_bucket = os.environ["staging_data_bucket"]
    topology_integrated_data_bucket = os.environ["integrated_data_bucket"]

    logging.info(event)

    event_detail = event["detail"]
    objects = json.loads(event_detail["objects"])

    for object_key in objects:
        logging.info(f"Processing {object_key}")

        topology_content = s3.get_object(
            Bucket=topology_staging_data_bucket, Key=object_key)["Body"].read()

        json_topo = json.loads(topology_content.decode("utf-8"))

        new_file_name = object_key.replace(".json", ".parquet")
        df = pd.json_normalize(json_topo)

        if 'location' in object_key:
            #the location.json contains decimal vlaues, which need to be mapped before they can be stored
            cols = df.columns
            for c in cols:
                try:
                    df[c] = pd.to_numeric(df[c])
                except:
                    pass

        os.makedirs(f"/tmp/{new_file_name}".rsplit('/', 1)[0], exist_ok=True)
        write(f"/tmp/{new_file_name}", df, compression='SNAPPY')

        try:
            s3.upload_file(f"/tmp/{new_file_name}", topology_integrated_data_bucket, f"{new_file_name}")
        except ClientError as e:
            logging.error(e)

    return {
        "statusCode": 200
    }
