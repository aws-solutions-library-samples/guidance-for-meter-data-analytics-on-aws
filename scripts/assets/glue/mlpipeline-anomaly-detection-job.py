import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame


import pandas as pd
from prophet import Prophet
import boto3

from pyspark.sql import functions as F
from pyspark.sql.functions import *
from pyspark.sql.types import *

args = getResolvedOptions(sys.argv, ['JOB_NAME', 'SOURCE_S3_BUCKET', 'SOURCE_S3_PATH', 'ANOMALY_S3_BUCKET', 'ANOMALY_S3_PATH', 'ANOMALY_S3_INFO_PATH', 'TIMESTAMP', 'MDA_DATABASE_ML', 'ANOMALY_RESULTS_TABLE_NAME', 'STACK_NAME'])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

SOURCE_BUCKET = args['SOURCE_S3_BUCKET'] 
PATH = args['SOURCE_S3_PATH'] 

ANOMALY_BUCKET = args['ANOMALY_S3_BUCKET'] #'meter-data-subset-flora'
ANOMALY_INFO_PATH = args['ANOMALY_S3_INFO_PATH'] #'anomaly-detection/1601b/anomalies_date_tracker'
ANOMALY_PATH = args['ANOMALY_S3_PATH'] #'anomaly-detection/1601b/anomaly3_parquet'
ANOMALY_BUCKET_URI = f's3://{ANOMALY_BUCKET}/{ANOMALY_PATH}'
TIMESTAMP = args['TIMESTAMP']
MDA_DATABASE_ML = args['MDA_DATABASE_ML']
ANOMALY_RESULTS_TABLE_NAME = args['ANOMALY_RESULTS_TABLE_NAME']

STACK_NAME = args['STACK_NAME']
ssm = boto3.client('ssm')
ParameterNameAnomaly = '/mlpipeline/'+STACK_NAME+'/Anomaly/LastDatetime'
LASTTIMESTAMP = ssm.get_parameter(Name=ParameterNameAnomaly)['Parameter']['Value']


df = spark.read.load(f"s3://{SOURCE_BUCKET}/{PATH}")


df = df.select('meter_id', 'reading_value', col('reading_date_time').alias('reading_datetime'))
df = df.groupBy('meter_id', to_date('reading_datetime').alias('date')).sum('reading_value').withColumnRenamed('sum(reading_value)','aggregated_value')


# filter out meter_ids with less than ten data points (cannot be less than two)
df_rare = df.groupBy("meter_id").count().withColumnRenamed("count", "n").filter(col("n") <= 10) 
meter_rare = df_rare.select("meter_id").rdd.flatMap(lambda x: x).collect()
df = df.filter(~F.col("meter_id").isin(meter_rare))

df = df.withColumn("is_weekend", dayofweek("date").isin([1,7]).cast("int"))
df = df.withColumnRenamed('date','ds').withColumnRenamed('aggregated_value','y').withColumnRenamed('is_weekend','weekend')


def get_previous_anomaly_dates():
    try:
        df_previous_anomaly_dates = spark.read.load(f's3://{ANOMALY_BUCKET}/{ANOMALY_INFO_PATH}/{LASTTIMESTAMP}')
    except:
        schema_anomaly_dates = StructType([
            StructField('meter_id', StringType(), True),
            StructField('max_ds', DateType(), True)
        ])
        df_previous_anomaly_dates = spark.createDataFrame([], schema_anomaly_dates)
    return df_previous_anomaly_dates

# function to get dataframe with meter_id, and max_ds (if exists)
def get_previous_anomaly_comparison(df_previous, df_new):
    df_previous = df_previous.select(col("meter_id").alias('prev_meter_id'), col("max_ds").alias("prev_max_ds"))
    df_left_join = df_new.join(df_previous, df_new.meter_id == df_previous.prev_meter_id,how='left')
    return df_left_join

df_max_ds = df.groupBy('meter_id').agg(F.max("ds").alias("max_ds"))
df_prev_anomalies_max_ds = get_previous_anomaly_dates()
df_prev_anomalies_comparison = get_previous_anomaly_comparison(df_prev_anomalies_max_ds, df_max_ds)
df_prev_anomalies_comparison = df_prev_anomalies_comparison.select(col('meter_id'), col('max_ds'), col('prev_max_ds'))

spark.conf.set("spark.sql.broadcastTimeout", 7200)

df_joined = df.join(df_prev_anomalies_comparison, ['meter_id'], how='left') 
df = df_joined
df.show()

result_schema =StructType([
    StructField('ds',DateType()),
    StructField('meter_id',StringType()),
    StructField('consumption',FloatType()),
    StructField('yhat',FloatType()),
    StructField('yhat_upper',FloatType()),
    StructField('yhat_lower',FloatType()),
    StructField('anomaly',IntegerType()),
    StructField('importance',FloatType())
])


def forecast_meter_id( history_pd: pd.DataFrame ) -> pd.DataFrame:
    
    def calculate(history_pd, prev_date):
        history_pd = history_pd.dropna()

        m = Prophet(
            daily_seasonality=False, 
            yearly_seasonality=True, 
            weekly_seasonality=True,
            seasonality_mode='multiplicative',
            interval_width=.98,
            changepoint_range=.8)
        m.add_country_holidays(country_name='US') #TODO adapt later to other countries
        m.add_regressor('weekend') 

        # train the model
        m.fit( history_pd )
        
        predict_pd = history_pd
        if prev_date is not None:
            predict_pd = predict_pd[predict_pd.ds > prev_date]

        # make predictions
        forecast = m.predict(predict_pd)  
        
        predict_pd = predict_pd[['ds','y']]
        predict_pd['ds'] = pd.to_datetime(predict_pd['ds'])
        forecast = forecast.merge(predict_pd, on='ds')
        forecast = forecast.rename(columns={"y": "consumption"})
        
        forecast['meter_id'] = history_pd['meter_id'].iloc[0]

        forecast['anomaly'] = 0
        forecast.loc[forecast['consumption'] > forecast['yhat_upper'], 'anomaly'] = 1
        forecast.loc[forecast['consumption'] < forecast['yhat_lower'], 'anomaly'] = -1

        # anomaly importance
        forecast['importance'] = 0
        forecast.loc[forecast['anomaly'] == 1, 'importance'] = \
            (forecast['consumption'] - forecast['yhat_upper']) / forecast['consumption']
        forecast.loc[forecast['anomaly'] == -1, 'importance'] = \
            (forecast['yhat_lower'] - forecast['consumption']) / forecast['consumption']

        # return expected dataset
        return forecast[ ['ds', 'meter_id', 'consumption', 'yhat', 'yhat_upper', 'yhat_lower', 'anomaly', 'importance'] ] 
    
    meter_id = history_pd['meter_id'].iloc[0]
    
    meter_id_exists = False
    if history_pd['prev_max_ds'].iloc[0] is not None:
        meter_id_exists = True
    
    # create empty dataframe
    forecast = pd.DataFrame(columns=['ds', 'meter_id', 'consumption', 'yhat', 'yhat_upper', 'yhat_lower', 'anomaly', 'importance'])
    
    # if meter_id not included in previous anomalies, then calculate all anomalies for the whole timeframe of this meter
    if not meter_id_exists:
        forecast = calculate(history_pd[['meter_id','ds','y','weekend']], None)
    
    # if meter_id is included in previous anomalies
    if meter_id_exists:
        max_date_previous = history_pd['prev_max_ds'].iloc[0]
        max_date = history_pd['max_ds'].iloc[0]
        # if max_date <= max_date_previous: do nothing, return empty df
        if max_date > max_date_previous:
            forecast = calculate(history_pd[['meter_id','ds','y','weekend']], max_date_previous)
            
    return forecast

results = (
    df
        .groupBy('meter_id')
        .applyInPandas(forecast_meter_id, schema=result_schema)
    )
    
results.show()
    

DyF = DynamicFrame.fromDF(results, glueContext, "results")

write_sink = glueContext.getSink(
  path=f's3://{ANOMALY_BUCKET}/{ANOMALY_PATH}',
  connection_type="s3",
  updateBehavior="UPDATE_IN_DATABASE",
  partitionKeys=[],
  compression="snappy",
  enableUpdateCatalog=True,
  transformation_ctx="write_sink",
  options = {
        "groupFiles": "inPartition",
        "groupSize": "104857600" # 104857600 bytes (100 MB)
  }
)
write_sink.setCatalogInfo(
  catalogDatabase=MDA_DATABASE_ML, catalogTableName=ANOMALY_RESULTS_TABLE_NAME
)
write_sink.setFormat("glueparquet")
write_sink.writeFrame(DyF)


df_anomalies_max_ds = results.groupBy('meter_id').agg(F.max("ds").alias("max_ds"))

# join with df_prev_anomalies_max_ds
df_prev_anomalies_max_ds = df_prev_anomalies_max_ds.select('meter_id',col('max_ds').alias('prev_max_ds'))
joined_max_df = df_prev_anomalies_max_ds.join(df_anomalies_max_ds, ['meter_id'], "outer")
joined_max_df = joined_max_df.withColumn("max_ds_both", greatest(joined_max_df.prev_max_ds,joined_max_df.max_ds))
max_df = joined_max_df.select(col('meter_id'),col('max_ds_both').alias('max_ds'))

max_df.write.parquet(f's3://{ANOMALY_BUCKET}/{ANOMALY_INFO_PATH}/{TIMESTAMP}')

ssm_response = ssm.put_parameter(Name=ParameterNameAnomaly,Value=str(TIMESTAMP),Type='String',Overwrite=True)

job.commit()