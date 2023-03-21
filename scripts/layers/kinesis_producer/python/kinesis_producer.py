import boto3
import json
import logging
import random
import time
import operator
import itertools

# Kinesis Limits
# (https://docs.aws.amazon.com/kinesis/latest/APIReference/API_PutRecord.html)
MAX_BYTES_PER_RECORD = 1000*1024  # 1 MB, accounting for record key in request
MAX_BYTES_PER_REQUEST = int(4.5*1024*1024) # 4.5 MB, accounting for other info in request
MAX_BATCH_SIZE = 500 #current maximum allowed

kinesis = boto3.client('kinesis')

logger = logging.getLogger()

class SimpleJsonRecordAggregator(object):
    def __init__(self, max_size=MAX_BYTES_PER_RECORD, aggregate_delimiter=""):
        """Create a new empty aggregator."""

        if max_size > MAX_BYTES_PER_RECORD:
            raise ValueError('Invalid max_size %d exceeds maximum value %d' %
                             (max_size, MAX_BYTES_PER_RECORD))
        self.max_size=max_size
        self.aggregate_delimiter = aggregate_delimiter
        self.full_size = 0

        self.records = {} # dictionary of records arrays
        self.callbacks = []

    def on_record_complete(self, callback, executor=lambda routine: routine()):
        if callback not in self.callbacks:
            self.callbacks.append((callback, executor))

    def add_record(self, partition_key, record):
        if self.should_flush(partition_key, record):
            logger.debug("Now flushing records: %s", self.records)
            self.flush()

        data  = json.dumps(record)
        data_size = len(data)

        if partition_key not in self.records or not self.records[partition_key]:
            self.records[partition_key] = {
                "records": "",
                "size": 0
            }

        self.records[partition_key]['records'] = \
            self.aggregate_delimiter.join([self.records[partition_key]['records'], data])
        self.records[partition_key]['size'] += data_size
        self.full_size += data_size

    def should_flush(self, partition_key, record):
        data  = json.dumps(record)
        data_size = len(data)

        return self._check_current_size(partition_key) + data_size > self.max_size \
            or self.full_size + data_size > MAX_BYTES_PER_REQUEST \
            or self._check_current_number_of_keys(partition_key) > MAX_BATCH_SIZE

    def flush(self):
        if self.callbacks:
            records_to_send = self.get_records_to_flush()
            self.records = {}
            self.full_size = 0
            for (callback, executor) in self.callbacks:
                executor(callback(records_to_send))

    def get_records_to_flush(self):
        return list(map(
            lambda internal_record: {
                'PartitionKey': internal_record[0],
                'Data': internal_record[1]['records']
            }, self.records.items()))

    def _check_current_number_of_keys(self, key):
        number_of_keys = len(self.records)
        if key in self.records and self.records[key]:
            return number_of_keys
        else:
            return number_of_keys + 1

    def _check_current_size(self, key):
        if key in self.records and self.records[key]:
            return self.records[key]['size']
        else:
            return 0

def write_kinesis(stream_name, records, mapper = lambda record:record, should_aggregate_records = True, retries = 5):
    failed_records_count = 0
    records = list(map(lambda record: _map_and_encode(record, mapper), records))
    if should_aggregate_records:
        records = aggregate_records(records)

    kinesis_batches = [records[x:x + MAX_BATCH_SIZE] for x in range(0, len(records), MAX_BATCH_SIZE)]

    for kinesis_batch in kinesis_batches:
        logger.debug("Sending request of size: %d", sum(len(r['Data']) for r in kinesis_batch))
        failed_records_count += kinesis_put_records(kinesis_batch, stream_name, retries)
    return failed_records_count


def aggregate_records(records):
    optimized_records = sorted(records, key=operator.itemgetter("PartitionKey"))
    for key, records in itertools.groupby(records, key=operator.itemgetter("PartitionKey")):
        optimized_records.append({
            "PartitionKey": key,
            "Data": _encode_data("".join([record["Data"].decode('utf-8') for record in records]))
        })
    return optimized_records

def _map_and_encode (record, mapper):
    record = mapper(record)
    logger.debug("mapped record: %s", record)
    return {
        'Data': _encode_data(record['Data']),
        'PartitionKey': record['PartitionKey']
    }
def _encode_data(data):
    if not isinstance(data, str):
        data = json.dumps(data)
    return data.encode('utf-8')

def kinesis_put_records(kinesis_records, stream_name, attempt=0, retries = 5):
    result = {}
    try:
        if attempt > retries:
            logger.critical("exhausted attempts, unable to insert records: %s", kinesis_records)
            return len(kinesis_records)

        if attempt:
            # Exponential back-off
            time.sleep(2 ** attempt * random.uniform(0, 0.1)) # nosec

        result = kinesis.put_records(StreamName=stream_name, Records=kinesis_records)

        status = result['ResponseMetadata']['HTTPStatusCode']
        logger.info("Processed %d records. WriteRecords Status: %s", len(kinesis_records), status)

        failed_record_count = result['FailedRecordCount']
        if failed_record_count:
            logger.warning('Warning: Retrying failed records with response: %s', json.dumps(result))
            failed_records = []
            for i, record in enumerate(result['Records']):
                if record.get('ErrorCode'):
                    failed_records.append(kinesis_records[i])

            # Recursive call
            attempt += 1
            return kinesis_put_records(failed_records, stream_name, attempt)

        return 0

    except Exception:
        logger.error("Was unable to put records", e)
        if result is not None:
            logger.warning("Error result: %s", result)
        return len(kinesis_records)