import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame

from pyspark.sql import functions as F
from pyspark.sql.functions import *
from pyspark.sql.functions import lit
from datetime import datetime, timedelta
from pyspark.sql.functions import row_number, monotonically_increasing_id, size
from pyspark.sql import Window


args = getResolvedOptions(sys.argv, ['JOB_NAME', 'INFERENCE_OUTPUT_S3_URI', 'UTIL_S3_URI', 'TRAINING_TIME_FRAME', 'TARGET_S3_BUCKET', 'TARGET_S3_PATH', 'TIMESTAMP', 'MDA_DATABASE_ML', 'INFERENCE_RESULTS_TABLE_NAME', 'MODEL_NAME'])  

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

TARGET_BUCKET = args['TARGET_S3_BUCKET'] 
TARGET_PATH = args['TARGET_S3_PATH'] 
INFERENCE_OUTPUT_S3_URI = args['INFERENCE_OUTPUT_S3_URI']
UTIL_S3_URI = args['UTIL_S3_URI']
TIMESTAMP = args['TIMESTAMP']

ML_GLUE_DB = args['MDA_DATABASE_ML']
INFERENCE_RESULTS_TABLE_NAME = args['INFERENCE_RESULTS_TABLE_NAME']
MODEL_NAME = args['MODEL_NAME']

TARGET_URI = f's3://{TARGET_BUCKET}/{TARGET_PATH}' 

output_df = spark.read.json(INFERENCE_OUTPUT_S3_URI)
util_df = spark.read.json(UTIL_S3_URI)

# combine util and output df based on the item order
util_df = util_df.withColumn("index", row_number().over(Window.orderBy(monotonically_increasing_id())))
output_df = output_df.withColumn("index", row_number().over(Window.orderBy(monotonically_increasing_id())))
joined_df = util_df.join(output_df, ['index'])
joined_df = joined_df.drop(joined_df.index)

# add forecast start datetime
joined_df = joined_df.select('*',size('target').alias('target_cnt'))
joined_df = joined_df.withColumn("forecast_start", (F.unix_timestamp("start") + F.col("target_cnt")*3600).cast('timestamp'))
joined_df = joined_df.drop(joined_df.target_cnt)

joined_df = joined_df.withColumn("model_name", lit(MODEL_NAME))

DyF = DynamicFrame.fromDF(joined_df, glueContext, "forecast_results")

write_sink = glueContext.getSink(
  path=TARGET_URI,
  connection_type="s3",
  updateBehavior="UPDATE_IN_DATABASE",
  partitionKeys=["model_name","forecast_start"],
  compression="snappy",
  enableUpdateCatalog=True,
  transformation_ctx="write_sink",
  options = {
        "groupFiles": "inPartition",
        "groupSize": "104857600" # 104857600 bytes (100 MB)
  }
)
write_sink.setCatalogInfo(
  catalogDatabase=ML_GLUE_DB, catalogTableName=INFERENCE_RESULTS_TABLE_NAME
)
write_sink.setFormat("glueparquet")
write_sink.writeFrame(DyF)



job.commit()