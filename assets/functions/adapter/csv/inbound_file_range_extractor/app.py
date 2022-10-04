# MIT No Attribution

# Copyright 2021 Amazon Web Services

# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import boto3
import json
import urllib.parse
import uuid

destination_queue = os.environ['TargetSQSQueue']
chunk_size = os.environ['ChunkSize']

s3 = boto3.client('s3')
sqs = boto3.resource('sqs')

def lambda_handler(event, context):
    total_chunks = 0
    try:
        for record in event['Records']:
            bucket = record['s3']['bucket']['name']
            key = urllib.parse.unquote_plus(record['s3']['object']['key'], encoding='utf-8')

            file_size = get_object_size(bucket, key)

            chunks = []
            start_range_bytes = 0
            end_range_bytes = min(chunk_size, file_size)
            while start_range_bytes < file_size:
                chunks.append({
                    "bucket": bucket,
                    "prefix": key,
                    "start-range-bytes": start_range_bytes,
                    "end-range-bytes": end_range_bytes,
                    "arrive_time": record["eventTime"]
                })
                start_range_bytes = end_range_bytes
                end_range_bytes = end_range_bytes + min(chunk_size, file_size - end_range_bytes)

            if not chunks:
                chunks.append({
                    "bucket": bucket,
                    "prefix": key
                })

            write_sqs(chunks)
            total_chunks = total_chunks + len(chunks)

        return {
            "statusCode": 200,
            "body": {
                "objects": str(len(event['Records'])),
                "chunk_size": str(chunk_size),
                "number_of_chuncks": str(len(total_chunks)),
            }
        }

    except Exception as e:
        print(e)
        print('Error with event object {} from bucket {}.'.format(key, bucket))
        raise e

def get_object_size(bucket, key):
    size = 0
    object_head_response = s3.head_object(Bucket=bucket, Key=key)
    if object_head_response:
        size = int(object_head_response['ResponseMetadata']['HTTPHeaders']['content-length'])
    return size

def write_sqs(chunks_list):
    queue = sqs.get_queue_by_name(QueueName=destination_queue)
    max_batch_size = 10 #current maximum allowed
    queue_batches = [chunks_list[x:x + max_batch_size] for x in range(0, len(chunks_list), max_batch_size)]
    message_group_id = str(uuid.uuid4())

    for queue_batch in queue_batches:
        entries = []
        for x in queue_batch:
            entry = {'Id': str(uuid.uuid4()),
                     'MessageBody': json.dumps(x),
                     'MessageGroupId': message_group_id}
            entries.append(entry)
        queue.send_messages(Entries=entries)