import boto3
import logging
import threading
import cfnresponse

logging.getLogger().setLevel(logging.INFO)


def copy_objects(source_bucket, dest_bucket, objects, source_prefix):
    s3 = boto3.client('s3')
    logging.info(f"Source {source_bucket}, Destination {dest_bucket}, Obj {objects}")
    for obj in objects:
        file_path = f"{source_prefix}{obj}"
        logging.info(file_path)
        copy_source = {'Bucket': source_bucket, 'Key': file_path}
        s3.copy_object(CopySource=copy_source, Bucket=dest_bucket, Key=obj)


def delete_objects(bucket, objects):
    s3 = boto3.client('s3')
    objects = {'Objects': [{'Key': obj} for obj in objects]}
    s3.delete_objects(Bucket=bucket, Delete=objects)


def timeout(event, context):
    logging.error('Execution is about to time out, sending failure response to CloudFormation')
    cfnresponse.send(event, context, cfnresponse.FAILED, {}, None)


def lambda_handler(event, context):
    print(event)
    timer = threading.Timer((context.get_remaining_time_in_millis() / 1000.00) - 0.5, timeout, args=[event, context])
    timer.start()
    try:
        source_bucket = event['ResourceProperties']['SourceBucket']
        source_prefix = event['ResourceProperties']['SourcePrefix']
        dest_bucket = event['ResourceProperties']['DestBucket']
        objects = [obj.strip() for obj in event['ResourceProperties']['Objects'].split(',')]
        if event['RequestType'] == 'Delete':
            delete_objects(dest_bucket, objects)
        else:
            copy_objects(source_bucket, dest_bucket, objects, source_prefix)
        status = cfnresponse.SUCCESS
    except Exception as e:
        logging.error('Exception: %s' % e, exc_info=True)
        status = cfnresponse.FAILED
    finally:
        timer.cancel()
        cfnresponse.send(event, context, status, {}, None)
