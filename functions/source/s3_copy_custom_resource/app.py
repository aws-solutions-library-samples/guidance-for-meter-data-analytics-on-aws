from crhelper import CfnResource
import logging
import boto3

helper = CfnResource()

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client('s3')
s3_resource = boto3.resource('s3')


def get_property(event, prop):
    return event['ResourceProperties'][prop]


def bucket_exists(bucket):
    try:
        s3.head_bucket(Bucket=bucket)
        return True
    except Exception:
        logging.info('Bucket {} does not exist'.format(bucket))
        return False


@helper.create
@helper.update
def on_create_update(event, _):
    logger.info("Received create/update event.")
    pass


@helper.delete
def on_delete(event, _):
    logger.info("Received delete event.")
    bucket = get_property(event, 'DestBucket')
    if bucket_exists(bucket):
        s3_bucket = s3_resource.Bucket(bucket)
        bucket_versioning = s3_resource.BucketVersioning(bucket)
        if bucket_versioning.status == 'Enabled':
            s3_bucket.object_versions.delete()
        else:
            s3_bucket.objects.all().delete()

    pass


def lambda_handler(event, context):
    helper(event, context)
