import sys
import random
import pyspark.sql.functions as f
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.dynamicframe import DynamicFrame
from awsglue.job import Job

args = getResolvedOptions(sys.argv, ["JOB_NAME"])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

logger = glueContext.get_logger()

# Dynamic Frame for raw data. Ran on a bookmark in order to avoid re-processing entire dataset. 
raw_dyf = glueContext.create_dynamic_frame.from_catalog(
    database="mda-dev", 
    table_name="raw_zone_scheduled", 
    transformation_ctx="raw_dyf"
)

# For testing
# raw_to_df = raw_dyf.toDF()
# logger.info("Row count is: " + str(raw_to_df.count()))

# Script generated for node ApplyMapping
raw_dyf_mapping = ApplyMapping.apply(
    frame=raw_dyf,
    mappings=[
        ("crrnt", "double", "crrnt", "double"),
        ("kva", "double", "kva", "double"),
        ("kvahcnsmptn", "double", "kvahcnsmptn", "double"),
        ("kvahrdng", "double", "kvahrdng", "double"),
        ("kw", "double", "kw", "double"),
        ("kwhcnsmptn", "double", "kwhcnsmptn", "double"),
        ("kwhrdng", "double", "kwhrdng", "double"),
        ("pf", "double", "pf", "double"),
        ("vltg", "double", "vltg", "double"),
        ("meter_id", "long", "meter_id", "long"),
        ("timestamp_add", "string", "timestamp_add", "string"),
    ],
    transformation_ctx="raw_dyf_mapping",
)

# TO DO: Partition list will be read from manifest file and the raw frame will be made from that.
partition_list = raw_dyf_mapping.toDF().select('timestamp_add').distinct().rdd.map(lambda x: x[0]).collect()

s3_partition_list = (str(partition_list)[1:-1])
print(s3_partition_list)

s3_predicate = f"timestamp_add IN ({s3_partition_list})"
print(s3_predicate)

logger.info(str(s3_predicate))

# Pass the partitions to be written to the processed dataset from the raw dataset. This allows Glue to only load and compare necessary partitions rather than entire dataset.
processed_dyf = glueContext.create_dynamic_frame.from_catalog(
    database="mda-dev", 
    table_name="processed_10mill", 
    transformation_ctx="processed_dyf", 
    push_down_predicate = s3_predicate
)

processed_dyf_mapping = ApplyMapping.apply(
    frame=processed_dyf,
    mappings=[
        ("crrnt", "double", "crrnt", "double"),
        ("kva", "double", "kva", "double"),
        ("kvahcnsmptn", "double", "kvahcnsmptn", "double"),
        ("kvahrdng", "double", "kvahrdng", "double"),
        ("kw", "double", "kw", "double"),
        ("kwhcnsmptn", "double", "kwhcnsmptn", "double"),
        ("kwhrdng", "double", "kwhrdng", "double"),
        ("pf", "double", "pf", "double"),
        ("vltg", "double", "vltg", "double"),
        ("meter_id", "long", "meter_id", "long"),
        ("timestamp_add", "string", "timestamp_add", "string"),
    ],
    transformation_ctx="processed_dyf_mapping",
)

# Drop Duplicates
raw_drop_duplicates = DynamicFrame.fromDF(
    raw_dyf_mapping.toDF().dropDuplicates(),
    glueContext,
    "raw_drop_duplicates",
)

# SQL for late arriving records / not writing duplicates
# Might need to make sure "processed_10mill" is created before the first job runs or it could error out.

raw_df = raw_drop_duplicates.toDF()
processed_df = processed_dyf_mapping.toDF()

processed_df.createOrReplaceTempView("processed_10mill")
raw_df.createOrReplaceTempView("raw_zone_scheduled")

# Only load new or late arriving records to older partitions where the record does not already exist.
result_df = spark.sql("""
SELECT r.*
FROM raw_zone_scheduled as r
WHERE r.meter_id NOT IN (
		SELECT p.meter_id
		FROM processed_10mill as p
		where (p.meter_id = r.meter_id AND p.timestamp_add = r.timestamp_add)
		)
"""
)

final_dyf = DynamicFrame.fromDF(result_df, glueContext, "final_dyf")

# Write late arriving data to processed table
final_dyf_write = glueContext.getSink(
    path="s3://cf-038810374562-meterdatasimulator/processed-10mill/",
    connection_type="s3",
    updateBehavior="UPDATE_IN_DATABASE",
    partitionKeys=["timestamp_add"],
    compression="snappy",
    enableUpdateCatalog=True,
    transformation_ctx="final_dyf_write",
)
final_dyf_write.setCatalogInfo(
    catalogDatabase="mda-dev", catalogTableName="processed_10mill"
)
final_dyf_write.setFormat("glueparquet")
final_dyf_write.writeFrame(final_dyf)
job.commit()
