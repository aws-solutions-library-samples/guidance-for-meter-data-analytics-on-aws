import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

from pyspark.sql import functions as F
from pyspark.sql.functions import *
from datetime import datetime, timedelta

from pyspark.sql import Window

args = getResolvedOptions(sys.argv, ['JOB_NAME', 'TARGET_S3_URI', 'SOURCE_S3_BUCKET', 'SOURCE_S3_PATH', 'TRAINING_TIME_FRAME', 'UTIL_S3_URI', 'MDA_DATABASE_INTEGRATED', 'SOURCE_TABLE_NAME'])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

TARGET_S3_URI = args['TARGET_S3_URI']
SOURCE_BUCKET = args['SOURCE_S3_BUCKET'] 
SOURCE_PATH = args['SOURCE_S3_PATH'] 
BUCKET_URI = f's3://{SOURCE_BUCKET}/{SOURCE_PATH}'

SOURCE_GLUE_DB = args['MDA_DATABASE_INTEGRATED']
SOURCE_GLUE_TABLE = args['SOURCE_TABLE_NAME']

UTIL_S3_URI = args['UTIL_S3_URI']

max_datetime = datetime.now()
training_time_frame = int(args['TRAINING_TIME_FRAME']) 
start_date = max_datetime - timedelta(days=training_time_frame)

dynamic_frame = glueContext.create_dynamic_frame_from_catalog(
    database = SOURCE_GLUE_DB, 
    table_name = SOURCE_GLUE_TABLE, 
    push_down_predicate = f"reading_type == 'kw' and (year > {start_date.year} or (year = {start_date.year} and (month > {start_date.month} or (month = {start_date.month} and day >= {start_date.day}))))", 
    transformation_ctx = "datasource")

df = dynamic_frame.toDF()
df = df.select('meter_id', 'reading_value', col('reading_date_time').alias('reading_datetime'))
df = (df
    .groupBy('meter_id', F.date_trunc('hour', 'reading_datetime').alias('date_hour'))
    .agg(F.sum('reading_value').alias('hourly_value'))
)


w = Window.partitionBy('meter_id').orderBy('date_hour')

sorted_list_df = df.withColumn(
            'target', F.collect_list('hourly_value').over(w)
        )\
        .groupBy('meter_id')\
        .agg(F.max('target').alias('target'), F.min("date_hour").alias("start"))

sorted_list_df = sorted_list_df.withColumn("start",sorted_list_df["start"].cast(StringType()))

# batch inference results in the same order 
sorted_list_df = sorted_list_df.orderBy('meter_id')

# save df with meter_id for later store_results job
sorted_list_df.write.json(UTIL_S3_URI)

sorted_list_df = sorted_list_df.drop('meter_id')

sorted_list_df.write.json(TARGET_S3_URI)

job.commit()