import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql.functions import *
from awsglue.dynamicframe import DynamicFrame


def write_json(meter_read_df, reading_type_to_extract, staging_database_name, staging_table_name):
    meter_read_dynf = DynamicFrame.fromDF(meter_read_df, glueContext, "meter_read_dynf")

    additional_options = {"enableUpdateCatalog": True}
    additional_options["partitionKeys"] = ["year", "month", "day", "hour"]

    glueContext.write_dynamic_frame_from_catalog(frame=meter_read_dynf,
                                                 database=staging_database_name,
                                                 table_name=staging_table_name,
                                                 transformation_ctx=f"meter_reads_staging_{reading_type_to_extract}",
                                                 additional_options=additional_options)


def transform_df(reading_type_to_extract, meter_read_df):
    return meter_read_df.select(
        col("device_id").alias("meter_id"),
        lit(reading_type_to_extract).alias("reading_type"),
        col(reading_type_to_extract).alias("reading_value"),
        col("time").alias("reading_date_time"),
        lit("B").alias("reading_source"),
        year(col("time").cast("timestamp")).alias("year"),
        month(col("time").cast("timestamp")).alias("month"),
        dayofmonth(col("time").cast("timestamp")).alias("day"),
        hour(col("time").cast("timestamp")).alias("hour")
    )


## @params: [JOB_NAME]
args = getResolvedOptions(sys.argv, ['JOB_NAME', "INBOUND_BUCKET", "STAGING_BUCKET", "MDA_DATABASE_STAGING",
                                     "STAGING_TABLE_NAME"])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

inbound_bucket_path = f"s3a://{args['INBOUND_BUCKET']}/data/historic/"
staging_bucket_path = f"s3://{args['STAGING_BUCKET']}/readings/json/"
table_name = args['STAGING_TABLE_NAME']
db_name = args['MDA_DATABASE_STAGING']

df = spark.read.option("header", True).csv(inbound_bucket_path)

reading_types = ["load", "crrnt", "pf", "kva", "kw", "vltg"]
for reading_type in reading_types:
    transformed_reading_type_df = transform_df(reading_type, df)
    write_json(meter_read_df=transformed_reading_type_df,
               reading_type_to_extract=reading_type,
               staging_database_name=db_name,
               staging_table_name=table_name)

# purge historic inbound folder
glueContext.purge_s3_path(inbound_bucket_path, options={"retentionPeriod": 0}, transformation_ctx="purge_inbound_files")

job.commit()
