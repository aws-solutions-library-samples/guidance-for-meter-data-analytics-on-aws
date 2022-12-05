import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
import pandas as pd

args = getResolvedOptions(sys.argv, ["JOB_NAME", "MDA_DATABASE_STAGING", "STAGING_TABLE_NAME", "INTEGRATED_BUCKET_NAME"])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

# Script generated for node Data Catalog table
DataCatalogtable_node1 = glueContext.create_dynamic_frame.from_catalog(
    database=args["MDA_DATABASE_STAGING"],
    table_name=args["STAGING_TABLE_NAME"],
    transformation_ctx="DataCatalogtable_node1",
    additional_options = {'useS3ListImplementation': True}
)

# Script generated for node ApplyMapping
ApplyMapping_node2 = ApplyMapping.apply(
    frame=DataCatalogtable_node1,
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

CustomMapping_node3 = Map.apply(frame = ApplyMapping_node2 , f = parse_date, transformation_ctx = "custommapping1")

# Script generated for node S3 bucket
S3bucket_node3 = glueContext.write_dynamic_frame.from_options(
    frame=ApplyMapping_node2,
    connection_type="s3",
    format="glueparquet",
    connection_options={
        "path": "s3://"+args["INTEGRATED_BUCKET_NAME"]+"/readings/parquet/",
        "partitionKeys": ["reading_type", "year", "month", "day", "hour"],
        "groupFiles": "inPartition",
        "groupSize": "104857600" # 104857600 bytes (100 MB)
    },
    format_options={"compression": "snappy"},
    transformation_ctx="S3bucket_node3",
)

job.commit()