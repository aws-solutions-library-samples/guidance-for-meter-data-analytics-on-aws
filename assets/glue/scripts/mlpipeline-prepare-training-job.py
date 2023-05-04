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

import boto3

## @params: [JOB_NAME]
args = getResolvedOptions(sys.argv, ['JOB_NAME', 'TARGET_S3_BUCKET', 'TARGET_S3_PATH', 'SOURCE_S3_BUCKET', 'SOURCE_S3_PATH', 'FORECAST_PERIOD', 'TRAINING_TIME_FRAME', 'MDA_DATABASE_INTEGRATED', 'SOURCE_TABLE_NAME', 'STACK_NAME'])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

TARGET_BUCKET = args['TARGET_S3_BUCKET']
TARGET_PATH = args['TARGET_S3_PATH'] 
SOURCE_BUCKET = args['SOURCE_S3_BUCKET'] 
SOURCE_PATH = args['SOURCE_S3_PATH']

SOURCE_GLUE_DB = args['MDA_DATABASE_INTEGRATED']
SOURCE_GLUE_TABLE = args['SOURCE_TABLE_NAME']

max_datetime = datetime.now()
training_time_frame = int(args['TRAINING_TIME_FRAME']) # 395
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
sorted_list_df = sorted_list_df.drop('meter_id')

# training and testing data 
# generate a new dataframe for training data
# num_test_windows = 2
# prediction_length = 7 * 24 
# forecast period is 7 days, 24 hours for hourly forecasts
# training data until 2*( max_datetime - 2*7 days)

forecast_period = int(args['FORECAST_PERIOD']) # 7
test_time_frame = 2*forecast_period

training_end = max_datetime - timedelta(days=test_time_frame)
training_df = df.filter(df.date_hour <= training_end)
training_list_df = training_df.withColumn(
            'target', F.collect_list('hourly_value').over(w)
        )\
        .groupBy('meter_id')\
        .agg(F.max('target').alias('target'), F.min("date_hour").alias("start"))

training_list_df = training_list_df.drop('meter_id')

# save to parquet in S3 
sorted_list_df.write.parquet(f"s3://{TARGET_BUCKET}/{TARGET_PATH}/test_data_parquet")
training_list_df.write.parquet(f"s3://{TARGET_BUCKET}/{TARGET_PATH}/train_data_parquet")

# configure training job resources
STACK_NAME = args['STACK_NAME']
ssm = boto3.client('ssm')
ParameterPrefixForecast = '/mlpipeline/'+STACK_NAME+'/Forecast/'

def get_folder_size(bucket, prefix):
    total_size = 0
    for obj in boto3.resource('s3').Bucket(bucket).objects.filter(Prefix=prefix):
        total_size += obj.size
    return total_size
    
size = get_folder_size(TARGET_BUCKET, TARGET_PATH)
# min 30 GB, otherwise use 2*size of folder
vol_size = 2*(size/1024**3) if 2*(size/1024**3)>30 else 30

ssm_response = ssm.put_parameter(Name=ParameterPrefixForecast+'TrainingVolumeSize',
        Value=str(vol_size),
        Type='String',
        Overwrite=True)


job.commit()