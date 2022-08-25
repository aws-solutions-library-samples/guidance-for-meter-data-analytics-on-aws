import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

args = getResolvedOptions(sys.argv, ["JOB_NAME", "MDA_DATABASE", "RAW_TABLE_NAME", "INTEGRATED_BUCKET_NAME"])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

# Script generated for node Data Catalog table
DataCatalogtable_node1 = glueContext.create_dynamic_frame.from_catalog(
    database=args["MDA_DATABASE"],
    table_name=args["RAW_TABLE_NAME"],
    transformation_ctx="DataCatalogtable_node1",
)

# Script generated for node ApplyMapping
ApplyMapping_node2 = ApplyMapping.apply(
    frame=DataCatalogtable_node1,
    mappings=[
        ("meter_id", "string", "meter_id", "string"),
        ("reading_value", "string", "reading_value", "double"),
        ("reading_type", "string", "reading_type", "string"),
        ("reading_date_time", "string", "reading_date_time", "string"),
        ("year", "string", "year", "int"),
        ("month", "string", "month", "int"),
        ("day", "string", "day", "int"),
        ("hour", "string", "hour", "int"),
    ],
    transformation_ctx="ApplyMapping_node2",
)

# Script generated for node S3 bucket
S3bucket_node3 = glueContext.write_dynamic_frame.from_options(
    frame=ApplyMapping_node2,
    connection_type="s3",
    format="glueparquet",
    connection_options={
        "path": "s3://"+args["INTEGRATED_BUCKET_NAME"]+"/readings/parquet/",
        "partitionKeys": ["year", "month", "day", "hour"],
    },
    format_options={"compression": "snappy"},
    transformation_ctx="S3bucket_node3",
)

job.commit()