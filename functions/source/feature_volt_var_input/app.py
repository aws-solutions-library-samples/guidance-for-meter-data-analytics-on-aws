import json, time, boto3, os, logging
from pyathena import connect
from datetime import datetime

sqs_client = boto3.client('sqs')

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    region = os.environ['AWS_REGION']
    queue_name = os.environ['volt_var_input_queue']
    bucket = os.environ['volt_var_bucket']
    glue_integrated_db = os.environ['glue_integration_db_name']
    reference_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    queue_url = sqs_client.get_queue_url(QueueName=queue_name)["QueueUrl"]

    transformer_cursor = connect(s3_staging_dir=f"s3://{bucket}/athena",
                                 region_name=region).cursor()

    tic = time.perf_counter()
    transformer_cursor.execute(f"SELECT id FROM {glue_integrated_db}.topology_data_integrated_distribution_transformer")
    toc = time.perf_counter()
    logging.info(f"Query time in {toc - tic:0.4f} seconds")

    counter = 0
    for transformer in transformer_cursor:
        counter += 1
        distribution_transformer_id = str(transformer[0])
        sqs_message = json.dumps({"distribution_transformer_id": distribution_transformer_id, "reference_time": reference_time})
        sqs_client.send_message(QueueUrl=queue_url, MessageBody=sqs_message)

    return {
        'body': json.dumps(f"Found {counter} distribution transformers.")
    }
