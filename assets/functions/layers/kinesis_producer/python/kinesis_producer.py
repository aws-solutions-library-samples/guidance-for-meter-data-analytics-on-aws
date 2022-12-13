import boto3
import json
import random
import time

kinesis = boto3.client('kinesis')

def write_kinesis(stream_name, records, retries):
    failed_records_count = 0

    max_batch_size = 500 #current maximum allowed
    kinesis_batches = [records[x:x + max_batch_size] for x in range(0, len(records), max_batch_size)]

    for kinesis_batch in kinesis_batches:
        kinesis_records = list(map(
            lambda reading:{
                'Data': encode_data(reading),
                'PartitionKey': reading['meter_id']
            }, kinesis_batch))
        failed_records_count = kinesis_put_records(kinesis_records, stream_name, retries)
    return failed_records_count

def encode_data(data):
    return json.dumps(data).encode('utf-8')

def kinesis_put_records(kinesis_records, stream_name, attempt=0, retries = 5):
    result = {}
    try:
        if attempt > retries:
            print("Error, unable to insert records:", kinesis_records)
            return len(kinesis_records)

        if attempt:
            # Exponential back-off
            time.sleep(2 ** attempt * random.uniform(0, 0.1))

        result = kinesis.put_records(StreamName=stream_name, Records=kinesis_records)

        print('Stream writing response {}'.format(result))
        status = result['ResponseMetadata']['HTTPStatusCode']
        print("Processed %d records. WriteRecords Status: %s" %
              (len(kinesis_records), status))

        failed_record_count = result['FailedRecordCount']

        if failed_record_count:
            print('Warning: Retrying failed records')
            failed_records = []
            for i, record in enumerate(result['Records']):
                if record.get('ErrorCode'):
                    failed_records.append(kinesis_records[i])

            # Recursive call
            attempt += 1
            return kinesis_put_records(failed_records, stream_name, attempt)

        return 0

    except Exception as err:
        print("Error:", err)
        if result is not None:
            print("Result:{}".format(result))
        return len(kinesis_records)