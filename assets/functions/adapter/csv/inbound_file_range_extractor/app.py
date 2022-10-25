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
import os

from datetime import datetime

destination_queue = os.environ['range_queue_url']
suggested_workers = int(os.environ['suggested_workers'])

sqs = boto3.client('sqs')

def lambda_handler(event, context):
    total_chunks = 0
    event_time = event['time'].replace('T', ' ').replace('Z', '')
    try:
        bucket = event['detail']['bucket']['name']
        key = urllib.parse.unquote_plus(event['detail']['object']['key'], encoding='utf-8')

        file_size = int(event['detail']['object']['size'])
        chunk_size = int(file_size/suggested_workers)

        chunks = []
        start_range_bytes = 0
        end_range_bytes = min(chunk_size, file_size)
        while start_range_bytes < file_size:
            chunks.append({
                "bucket": bucket,
                "prefix": key,
                "start-range-bytes": start_range_bytes,
                "end-range-bytes": end_range_bytes,
                "arrive_time": event_time
            })
            start_range_bytes = end_range_bytes
            end_range_bytes = end_range_bytes + min(chunk_size, file_size - end_range_bytes)

        if not chunks:
            chunks.append({
                "bucket": bucket,
                "prefix": key,
                "start-range-bytes": 0,
                "end-range-bytes": event['detail']['object']['size'],
                "arrive_time": event_time
            })

        write_sqs(chunks)

        return {
            "statusCode": 200,
            "body": {
                "chunk_size": str(chunk_size),
                "number_of_chuncks": len(chunks),
                "chuncks": chunks
            }
        }

    except Exception as e:
        print(e)
        print('Error with event object {}.'.format(json.dumps(event)))
        raise e


def write_sqs(chunks_list):
    max_batch_size = 10 #current maximum allowed
    queue_batches = [chunks_list[x:x + max_batch_size] for x in range(0, len(chunks_list), max_batch_size)]
    print('Queue batches len {}.'.format(len(queue_batches)))

    for queue_batch in queue_batches:
        entries = list(map(lambda queue_message: {'Id': str(uuid.uuid4()), 'MessageBody': json.dumps(queue_message)}, queue_batch))
        result = sqs.send_message_batch(QueueUrl=destination_queue,Entries=entries)
        print('Queue sending response {}.'.format(json.dumps(result)))