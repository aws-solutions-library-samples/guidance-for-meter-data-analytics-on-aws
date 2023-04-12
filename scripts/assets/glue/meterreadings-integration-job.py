import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
import pandas as pd

args = getResolvedOptions(sys.argv,
                          ["JOB_NAME", "MDA_STAGING_BUCKET", "MDA_DATABASE_STAGING", "MDA_DATABASE_INTEGRATED", "STAGING_TABLE_NAME",
                           "TARGET_TABLE_NAME", "INTEGRATED_BUCKET_NAME"])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

gyf = glueContext.create_dynamic_frame.from_options(
    connection_type="s3",
    connection_options={
        "paths": [f"s3://{args['MDA_STAGING_BUCKET']}/readings/json/"]
    },
    format="json", transformation_ctx="dyf",

# Script generated for node ApplyMapping
ApplyMapping_node2 = ApplyMapping.apply(
    frame=gyf,
    mappings=[
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
    ],
    transformation_ctx="ApplyMapping_node2",
)


def parse_date(df):
    dt = pd.to_datetime(df["reading_date_time"]).dt.strftime('%Y-%m-%d %H:%M:%S.%f')
    return dt


CustomMapping_node3 = Map.apply(frame=ApplyMapping_node2, f=parse_date, transformation_ctx="custommapping1")

# # Script generated for node S3 bucket
# S3bucket_node3 = glueContext.write_dynamic_frame.from_options(
#     frame=ApplyMapping_node2,
#     connection_type="s3",
#     format="glueparquet",
#     connection_options={
#         "path": "s3://"+args["INTEGRATED_BUCKET_NAME"]+"/readings/parquet/",
#         "partitionKeys": ["reading_type", "year", "month", "day", "hour"],
#         "groupFiles": "inPartition",
#         "groupSize": "104857600" # 104857600 bytes (100 MB)
#     },
#     format_options={"compression": "snappy"},
#     transformation_ctx="S3bucket_node3",
# )

write_sink = glueContext.getSink(
    path="s3://" + args["INTEGRATED_BUCKET_NAME"] + "/readings/parquet/",
    connection_type="s3",
    updateBehavior="UPDATE_IN_DATABASE",
    partitionKeys=["reading_type", "year", "month", "day", "hour"],
    compression="snappy",
    enableUpdateCatalog=True,
    transformation_ctx="write_sink",
    options={
        "groupFiles": "inPartition",
        "groupSize": "104857600"  # 104857600 bytes (100 MB)
    }
)

write_sink.setCatalogInfo(
    catalogDatabase=args["MDA_DATABASE_INTEGRATED"], catalogTableName=args["TARGET_TABLE_NAME"]
)
write_sink.setFormat("glueparquet")
write_sink.writeFrame(ApplyMapping_node2)

job.commit()
