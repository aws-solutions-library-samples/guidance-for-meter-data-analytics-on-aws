import sys
import random
import boto3
import pandas as pd
import pyspark.sql.functions as f
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.dynamicframe import DynamicFrame
from awsglue.job import Job

args = getResolvedOptions(sys.argv,
                          ["JOB_NAME", "MDA_DATABASE_STAGING", "MDA_DATABASE_INTEGRATED", "STAGING_TABLE_NAME",
                           "TARGET_TABLE_NAME", "INTEGRATED_BUCKET_NAME"])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

logger = glueContext.get_logger()

# Script generated for node Data Catalog table
DataCatalogtable_node1 = glueContext.create_dynamic_frame.from_catalog(
    database=args["MDA_DATABASE_STAGING"],
    table_name=args["STAGING_TABLE_NAME"],
    transformation_ctx="DataCatalogtable_node1",
    additional_options={'useS3ListImplementation': True}
)

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

part_list = source_map.toDF().select('reading_date_time').orderBy(f.desc('reading_date_time')).distinct().rdd.map(
    lambda x: x[0]).collect()

s3_partition_list = (str(part_list)[1:-1])

write_sink = glueContext.getSink(
    path="s3://" + args["INTEGRATED_BUCKET_NAME"] + "/readings/parquet/",
    connection_type="s3",
    updateBehavior="UPDATE_IN_DATABASE",
    partitionKeys=["reading_type", "year", "month", "day", "hour"],
    compression="snappy",
    enableUpdateCatalog=True,
    transformation_ctx="write_context",
    options={
        "groupFiles": "inPartition",
        "groupSize": "104857600"  # 104857600 bytes (100 MB)
    }
)

# Ensure data exists before loading target dataset in
if len(part_list) > 0 and source_map.count() > 0:
    s3_predicate = f"reading_date_time IN ({s3_partition_list})"

    print(s3_predicate)

    # Pass the partitions to be written to the processed dataset from the raw dataset. This allows Glue to only load and compare necessary partitions rather than entire dataset.
    target_dyf = glueContext.create_dynamic_frame.from_catalog(
        database=args["MDA_DATABASE_INTEGRATED"],
        table_name=args["TARGET_TABLE_NAME"],
        transformation_ctx="target_dyf",
        push_down_predicate=s3_predicate
    )

    target_map = ApplyMapping.apply(
        frame=target_dyf,
        mappings=mappings,
        transformation_ctx="target_map",
    )

    union_source = source_map.toDF()
    union_target = target_map.toDF()

    union_all = union_source.union(union_target)

    final_dyf = DynamicFrame.fromDF(union_all, glueContext, "final_dyf")

    write_sink.setCatalogInfo(
        catalogDatabase=args["MDA_DATABASE"], catalogTableName=args["TARGET_TABLE_NAME"]
    )
    write_sink.setFormat("glueparquet")
    write_sink.writeFrame(final_dyf)

    # Purge data older than 1 hour, after re-writing the partition. Any deleted data goes to purged folder in bucket
    glueContext.purge_table(
        args["MDA_DATABASE"],
        args["TARGET_TABLE_NAME"],
        options={
            "partitionPredicate": s3_predicate,
            "retentionPeriod": 1,
            "manifestFilePath": "s3://" + args["INTEGRATED_BUCKET_NAME"] + "/readings/purged/"
        },
        transformation_ctx="final_dyf"
    )

# Handle Job runs that might not process data for any reason. This ensures a Table is not purged on accident.
else:
    logger.info('No new Partitions or Rows to process...')
    write_sink.setCatalogInfo(
        catalogDatabase=args["MDA_DATABASE"], catalogTableName=args["TARGET_TABLE_NAME"]
    )
    write_sink.setFormat("glueparquet")
    write_sink.writeFrame(source_map)

job.commit()

# def parse_date(df):
#    dt = pd.to_datetime(df["reading_date_time"]).dt.strftime('%Y-%m-%d %H:%M:%S.%f')
#    return dt
#
#
#
#
# CustomMapping_node3 = Map.apply(frame = ApplyMapping_node2 , f = parse_date, transformation_ctx = "custommapping1")
#
## Script generated for node S3 bucket
# S3bucket_node3 = glueContext.write_dynamic_frame.from_options(
#    frame=ApplyMapping_node2,
#    connection_type="s3",
#    format="glueparquet",
#    connection_options={
#        "path": "s3://"+args["INTEGRATED_BUCKET_NAME"]+"/readings/parquet/",
#        "partitionKeys": ["year", "month", "day", "hour"],
#        "groupFiles": "inPartition",
#        "groupSize": "104857600" # 104857600 bytes (100 MB)
#    },
#    format_options={"compression": "snappy"},
#    transformation_ctx="S3bucket_node3",
# )
#
# job.commit()
