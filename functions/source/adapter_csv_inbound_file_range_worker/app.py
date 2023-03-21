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
import multiprocessing
import os
import threading

from kinesis_producer import write_kinesis, SimpleJsonRecordAggregator

kinesis_stream_name = os.environ["staging_record_stream"]
max_retries = int(os.getenv("max_stream_retries", "5"))
processes = int(os.getenv("max_stream_retries", "5"))
max_kinesis_records_batch = 1000

s3 = boto3.client("s3")

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# thread safe counter class
class Counter:
    # constructor
    def __init__(self):
        # initialize counter
        self._counter = 0
        self._lock = threading.Lock()

    # increment the counter
    def increment(self, count=1):
        if count:
            with self._lock:
                self._counter += count

    # get the counter value
    def value(self):
        return self._counter

_total_processed_records = Counter()
_total_failed_records = Counter()
_total_read_records = Counter()

_processes_collection = []

def lambda_handler(event, context):
    logger.debug("Processing event: " + json.dumps(event))
    failed_messages = []
    try:
        for record in event["Records"]:
            try:
                message = json.loads(record["body"])
                bucket = message["bucket"]
                prefix = message["prefix"]
                start_range = 0
                if "start-range" in message:
                    start_range = message["start-range"]

                if "end-range" in message and message["end-range"] != -1:
                    end_range = message["end-range"]
                else:
                    end_range = get_object_size(bucket, prefix)

                if logging.getLogger().isEnabledFor(logging.DEBUG):
                    row_count = count_rows(bucket, prefix, start_range, end_range)
                    logger.debug("Select row count: %d", row_count)

                produce_staging_records_intake(bucket, prefix, start_range, end_range)

            except Exception as e:
                failed_messages.append({"itemIdentifier": record["messageId"]})
                raise e
    except Exception as e:
        logging.warn("Error with event object %s", json.dumps(event))
        logging.exception("Error processing event")
        raise e

    if not _total_failed_records.value():
        return {
            "statusCode": 200,
            "body": {
                "processed": _total_processed_records.value(),
                "batchItemFailures": failed_messages,
                "failedStreamingRecordsCount": _total_failed_records.value()
            }
        }
    else:
        raise Exception("Some messages failed to be processed", json.dumps({
            "batchItemFailures": failed_messages,
            "failedStreamingRecordsCount": _total_failed_records.value()
        }))


def s3_select(bucket, prefix, expression, start_range, end_range,
              output_serialization={"JSON": {"RecordDelimiter": "\n"}}):
    response = s3.select_object_content(
        Bucket=bucket,
        Key=prefix,
        ExpressionType="SQL",
        Expression=expression,
        InputSerialization={
            "CSV": {
                "FileHeaderInfo": "USE",
                "FieldDelimiter": ",",
                "RecordDelimiter": "\n"
            }
        },
        OutputSerialization=output_serialization,
        ScanRange={
            "Start": start_range,
            "End": end_range
        },
    )
    return response


def count_rows(bucket, prefix, start_range, end_range):
    response = s3_select(bucket, prefix, """SELECT count(*) FROM s3object """, start_range, end_range,
                         {"CSV": {}})
    row_count = 0
    for payload in response["Payload"]:
        if records := payload.get("Records"):
            row_count = int(records["Payload"].decode("utf-8"))
    return row_count


def get_object_size(bucket, key):
    end_range = 0
    object_head_response = s3.head_object(Bucket=bucket, Key=key)
    if object_head_response:
        end_range = int(object_head_response["ResponseMetadata"]["HTTPHeaders"]["content-length"])
    return end_range

def produce_staging_records_intake (bucket, prefix, start_range, end_range):
    logger.info("Starting producer thread")
    agg = SimpleJsonRecordAggregator()
    agg.on_record_complete(callback=consume_staging_records_intake, executor= map_async)

    response = s3_select(bucket, prefix, "SELECT * FROM S3Object", start_range, end_range)
    """
    select_object_content() response is an event stream that can be looped to concatenate the overall result set
    Hence, we are joining the results of the stream in a string before converting it to a tuple of dict
    """
    cut_off = ""
    for index, payload in enumerate(response["Payload"]):
        if records := payload.get("Records"):
            staging_records = (cut_off + records["Payload"].decode("utf-8")).split("\n")
            cut_off = staging_records.pop()
            if cut_off.startswith("{") and cut_off.endswith("}"):
                staging_records.append(cut_off)
                cut_off = ""
            logger.debug("Adding records %d to aggregator", len(staging_records))
            staging_records = to_staging_stream_format(staging_records)
            _total_read_records.increment(len(staging_records))
            for some_staging_record in staging_records:
                agg.add_record(some_staging_record["meter_id"], some_staging_record)
    agg.flush()
    logger.info("Reading in consumer thread done now waiting for %d processes", len(_processes_collection))
    for process in _processes_collection:
        process.join()
    logger.info("Processing in consumer thread done, Processed %d out of %d total records, failed records so far is %d",
                _total_processed_records.value(), _total_read_records.value(), _total_failed_records.value())

def consume_staging_records_intake (staging_records):
    logger.debug("Will process : %d record", len(staging_records))
    write_records_to_kinesis(staging_records)
    logger.info("Processed %d out of %d total records, failed records so far is %d",
                _total_processed_records.value(), _total_read_records.value(), _total_failed_records.value())

def write_records_to_kinesis(staging_records):
    failed = write_kinesis(
        kinesis_stream_name, staging_records, should_aggregate_records = False, retries = max_retries)
    _total_failed_records.increment(failed)
    _total_processed_records.increment(sum(r["Data"].count("}") for r in staging_records))

def to_staging_stream_format(file_records):
    result = []
    for file_record in file_records:
        try:
            json_record = json.loads(file_record)
            unwanted_fields = ["time", "device_id", "measure_name", "arrival_time"]
            measures = {k: v for k, v in json_record.items() if k not in unwanted_fields}
            for measure_name, measure_value in measures.items():
                result.append({
                    "meter_id":json_record["device_id"],
                    "reading_type":measure_name,
                    "reading_value":measure_value,
                    "reading_date_time":json_record["time"][:-3],
                    "reading_source":"B"
                })

        except Exception:
            logging.exception("failed to unpack record: %s", file_record)
            pass
    return result

def to_kinesis_record(staging_record):
    return {"Data": staging_record, "PartitionKey": staging_record["meter_id"]}

def map_async(action_to_perform):
    process = multiprocessing.Process(target=action_to_perform, args=())
    process.start()
    _processes_collection.append(process)