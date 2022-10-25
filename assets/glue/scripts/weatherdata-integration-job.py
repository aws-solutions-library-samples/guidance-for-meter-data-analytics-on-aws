import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
import pandas as pd
from pyspark.sql.functions import *
from awsglue.dynamicframe import DynamicFrame

args = getResolvedOptions(sys.argv, ["JOB_NAME", "MDA_DATABASE", "STAGING_TABLE_NAME", "INTEGRATED_BUCKET_NAME"])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)


def parse_date(df):
    return pd.to_datetime(df["time"]).dt.strftime('%Y-%m-%d %H:%M:%S.%f')


# Script generated for node S3 bucket
S3bucket_node1 = glueContext.create_dynamic_frame.from_catalog(
    database=args["MDA_DATABASE"],
    table_name=args["STAGING_TABLE_NAME"],
    transformation_ctx="S3bucket_node1",
)

# Script generated for node ApplyMapping
ApplyMapping_node2 = ApplyMapping.apply(
    frame=S3bucket_node1,
    mappings=[
        ("time", "string", "time", "timestamp"),
        ("temp", "double", "temperature", "double"),
        ("dwpt", "double", "dew_point", "double"),
        ("rhum", "double", "relative_humidity", "double"),
        ("prcp", "string", "precipitation", "double"),
        ("snow", "string", "snow_depth", "double"),
        ("wdir", "double", "wind_direction", "double"),
        ("wspd", "double", "wind_speed", "double"),
        ("wpgt", "string", "wind_gust", "double"),
        ("pres", "string", "sealevel_air_pressure", "double"),
        ("tsun", "string", "sunshine_hours", "double"),
        ("coco", "string", "weather_condition_code", "double"),
    ],
    transformation_ctx="ApplyMapping_node2",
)

# date is used as a partition key
df = ApplyMapping_node2.toDF()
df = df.withColumn("date", col("time").substr(1, 10))

enriched_df = DynamicFrame.fromDF(df, glueContext, "enriched_df")

# Script generated for node S3 bucket
S3bucket_node3 = glueContext.getSink(
    path=f"s3://{args['INTEGRATED_BUCKET_NAME']}/weather/",
    connection_type="s3",
    partitionKeys=["date"],
    compression="snappy",
    transformation_ctx="S3bucket_node3",
)

S3bucket_node3.setFormat("glueparquet")
S3bucket_node3.writeFrame(enriched_df)
job.commit()
