import sys
import uuid
import boto3
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql.functions import *
from awsglue.context import GlueContext
from awsglue.dynamicframe import DynamicFrame
from awsglue.job import Job

try:
    args = getResolvedOptions(sys.argv, ['JOB_NAME', 'timestream_database', 'timestream_table', 'bucket', 'request_id', 'start_date', 'end_date', 'dynamodb_table', 'partition_count', 'region'])
    s3_client = boto3.client('s3')
    dynamodb_resource = boto3.resource('dynamodb')
    dynamodb_table = args['dynamodb_table']
    dtable = dynamodb_resource.Table(dynamodb_table)

    sparkContext = SparkContext()
    glueContext = GlueContext(sparkContext)
    sparkSession = glueContext.spark_session
    glueJob = Job(glueContext)
    glueJob.init(args['JOB_NAME'], args)
    
    request_id = args['request_id']
    timestream_database = args['timestream_database']
    timestream_table = args['timestream_table']
    dynamodb_table = args['dynamodb_table']
    partition_count = int(args['partition_count'])
    region = args['region']
    bucket = args['bucket']
    start_date = args['start_date']
    end_date = args['end_date']
    results_path = 'data/sftp/'
    
    # Update dynamodb status to running
    dtable.update_item(
        Key= {'request_id': request_id},
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={':status': 'running'},
        UpdateExpression='SET #status = :status'
    )

    #Fetch data async, passing in partition vars
    # fmt: off
    records_query = (# nosec
    f"""( 
    	select
    		time, arrival_time, device_id, measure_name, load, crrnt, pf, kva, kw, vltg
    	from "{{timestream_database}}"."{{timestream_table}}"
    	where time >= '{{start_date}}'
    	and time <= '{{end_date}}'
    	)""") \
    .format(
    	timestream_database=timestream_database,
    	timestream_table=timestream_table,
    	start_date=start_date,
    	end_date=end_date
    )
    # fmt: on

    datasource0 = sparkSession.read \
        .format('jdbc') \
        .option('url', 'jdbc:timestream://Region=' + region) \
        .option('dbtable', records_query) \
        .option('driver', 'software.amazon.timestream.jdbc.TimestreamDriver') \
        .option('partitionColumn', 'time') \
        .option('lowerBound', start_date) \
        .option('upperBound', end_date) \
        .option('numPartitions', partition_count) \
        .option('fetchsize', 1000) \
        .load()
    
    datasource1 = datasource0 \
        .withColumn('time', date_format(col('time'), 'yyyy-MM-dd HH:mm:ss.SSSSSS')) \
        .withColumn('arrival_time', date_format(col('arrival_time'), 'yyyy-MM-dd HH:mm:ss.SSSSSS'))
    
    # Convert to Dynamic Frame
    dynamicframe0 = DynamicFrame.fromDF(datasource1, glueContext, 'dynamicframe0')
    
    singlepart_dynamicframe0 = dynamicframe0.repartition(1)
    
    # Write to s3
    DataSink0 = glueContext.write_dynamic_frame.from_options(
        frame = singlepart_dynamicframe0,
        connection_type = 's3',
        format = 'csv',
        format_options = {'quoteChar': -1},
        connection_options = {
            'path': 's3://' + bucket + '/' + results_path + request_id,
            'compression': 'gzip'
        }
    )
    
    # Get file name
    s3_response = s3_client.list_objects(Bucket=bucket, Prefix=results_path + request_id)
    sftp_location = s3_response['Contents'][0]['Key'].replace(results_path,'')
    
    # Update dynamodb status to completed and location of file
    dtable.update_item(
        Key= {'request_id': request_id},
        ExpressionAttributeNames={
            '#status': 'status',
            '#sftp_location': 'sftp_location'
        },
        ExpressionAttributeValues={
            ':status': 'completed',
            ':sftp_location': sftp_location
        },
        UpdateExpression='SET #status = :status, #sftp_location = :sftp_location'
    )
    
    glueJob.commit()

except Exception as e:
    # Update dynamodb status to failed
    dtable.update_item(
        Key= {'request_id': request_id},
        ExpressionAttributeNames={
            '#status': 'status',
            '#job_detail': 'job_detail',
            '#reason': 'reason'
        },
        ExpressionAttributeValues={
            ':status': 'failed',
            ':reason': str(e)
        },
        UpdateExpression='SET #status = :status, #job_detail.#reason = :reason'
    )
    
