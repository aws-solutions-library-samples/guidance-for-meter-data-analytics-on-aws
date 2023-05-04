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
import logging
import urllib.parse
import uuid
import os

destination_queue = os.environ["range_queue_url"]
suggested_workers = int(os.environ["max_workers"])
# Chunks should be able to go through 1 kinesis shard in 4 mins (4*60).
# A shard can take up to 1 MB (1000 * 1000 bytes) per second
max_throughput_for_1_worker_in_5_mins = 5 * 60 * 1000 * 1000

# While the number of messages that an Amazon SQS queue can store is unlimited.
# For most standard queues, there can be a maximum of approximately 120,000 in flight messages.
# We'll guard the queue against 50K messages.
max_sqs_inflight_per_file = 50_000

sqs = boto3.client("sqs")
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.debug("Processing event: " + json.dumps(event))
    event_time = event["time"].replace("T", " ").replace("Z", "")
    try:
        bucket = event["detail"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(event["detail"]["object"]["key"], encoding="utf-8")

        file_size = int(event["detail"]["object"]["size"])
        chunk_size = calculate_chunk_size(file_size)
        logger.info("chunk size: %d", chunk_size)

        chunks = []
        start_range_bytes = 0
        end_range_bytes = min(chunk_size, file_size)
        logger.debug("File Size: %d, Chunk Size: %d, End Range Bytes: %d", file_size, chunk_size, end_range_bytes)
        while start_range_bytes < file_size:
            chunks.append({
                "bucket": bucket,
                "prefix": key,
                "start-range": start_range_bytes,
                "end-range": end_range_bytes,
                "arrive_time": event_time
            })
            start_range_bytes = end_range_bytes
            end_range_bytes = end_range_bytes + min(chunk_size, file_size - end_range_bytes)
            logger.debug("Chunk Start Range Bytes: %d, End Range Bytes: %d", start_range_bytes, end_range_bytes)

        if not chunks:
            chunks.append({
                "bucket": bucket,
                "prefix": key,
                "start-range-bytes": 0,
                "end-range-bytes": event["detail"]["object"]["size"],
                "arrive_time": event_time
            })

        logger.info("created %d chunks to process", len(chunks))
        write_sqs(chunks)

        return {
            "statusCode": 200,
            "body": {
                "chunk_size": chunk_size,
                "number_of_chunks": len(chunks)
            }
        }

    except Exception as e:
        logging.warn("Error with event object %s", json.dumps(event))
        logging.exception("Error processing event")
        raise e


def calculate_chunk_size(file_size):
    suggested_chunk_size = int(file_size / suggested_workers)
    guard_against_sqs_overload = int(file_size / max_sqs_inflight_per_file)

    chunk_size = suggested_chunk_size \
        if suggested_chunk_size < max_throughput_for_1_worker_in_5_mins \
        else max_throughput_for_1_worker_in_5_mins
    chunk_size = chunk_size \
        if chunk_size > guard_against_sqs_overload \
        else guard_against_sqs_overload

    return chunk_size

def write_sqs(chunks_list):
    max_batch_size = 10 #current maximum allowed
    queue_batches = [chunks_list[x:x + max_batch_size] for x in range(0, len(chunks_list), max_batch_size)]
    logger.debug("Queue batches len %d", len(queue_batches))

    for queue_batch in queue_batches:
        entries = list(map(lambda queue_message: {"Id": str(uuid.uuid4()), "MessageBody": json.dumps(queue_message)}, queue_batch))
        result = sqs.send_message_batch(QueueUrl=destination_queue,Entries=entries)
        logger.debug("Queue sending response %s", json.dumps(result))