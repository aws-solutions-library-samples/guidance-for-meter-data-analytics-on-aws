import sys
import json
import boto3
from datetime import datetime
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.dynamicframe import DynamicFrame
from awsglue.job import Job

args = getResolvedOptions(sys.argv, ["JOB_NAME","MDA_DATABASE_INTEGRATED", "TARGET_TABLE_NAME","INTEGRATED_BUCKET_NAME"])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
logger = glueContext.get_logger()

# Get the service resource
sqs = boto3.resource('sqs')

# Get the queue
queue = sqs.get_queue_by_name(QueueName='late-arriving-sqs')

partition_list = []

for message in queue.receive_messages():
    j = json.loads(message.body)
    late_partition = j['responsePayload']['body']['result']['late_arriving'][0]['late_partition_time']
    date_convert = late_partition.replace(',', '')
    dt = datetime.strptime(date_convert, '%m/%d/%Y %H:%M:%S.%f')
    s3_list = "year={} AND month={} AND day={} AND hour={}".format(dt.year, dt.month, dt.day, dt.hour)

    partition_list.append(s3_list)

print(partition_list)

logger.info("found " + str(len(partition_list)) + " partitions with late arriving data. Running cleanup job now.")

for x in range(len(partition_list)):
    print(partition_list[x])

    job = Job(glueContext)
    job.init(args["JOB_NAME"], args)

    # Script generated for node Data Catalog table
    DataCatalogtable_node1 = glueContext.create_dynamic_frame.from_catalog(
        database=args["MDA_DATABASE_INTEGRATED"],
        table_name=args["TARGET_TABLE_NAME"],
        transformation_ctx="DataCatalogtable_node1",
        additional_options = {'useS3ListImplementation': True},
        push_down_predicate = "({})".format(partition_list[x])
    )

    logger.info("processing partition: " + str(partition_list[x]))

    mappings = [
        ("meter_id", "string", "meter_id", "string"),
        ("reading_value", "string", "reading_value", "double"),
        ("reading_type", "string", "reading_type", "string"),
        ("reading_date_time", "string", "reading_date_time", "timestamp"),
        ("unit", "string", "unit", "string"),
        ("obis_code", "string", "obis_code", "string"),
        ("phase", "string", "phase", "string"),
        ("reading_source", "string", "reading_source", "string"),
        ("year", "string", "year", "int"),
        ("month", "string", "month", "int"),
        ("day", "string", "day", "int"),
        ("hour", "string", "hour", "int"),
    ]

    # Script generated for node ApplyMapping
    source_map = ApplyMapping.apply(
        frame=DataCatalogtable_node1,
        mappings=mappings,
        transformation_ctx="ApplyMapping_node2",
    )

    spark.conf.set("spark.sql.sources.partitionOverwriteMode","dynamic")
    source_map.toDF().write.mode("overwrite").format("parquet").partitionBy("reading_type", "year", "month", "day", "hour").save("s3://"+args["INTEGRATED_BUCKET_NAME"]+"/readings/parquet/")

    x += 1

    if len(partition_list) < 1:
        logger.info("Finished processing partitions.")
    else:
        logger.info("Moving to next partition...")

    job.commit()

logger.info("Cleanup job completed, deleting items from SQS queue...")

for message in queue.receive_messages():
    # Wipe the SQS queue
    message.delete()

logger.info("SQS queue items deleted.")