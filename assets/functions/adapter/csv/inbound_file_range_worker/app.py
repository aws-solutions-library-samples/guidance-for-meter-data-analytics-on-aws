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
import os
import random
import time

kinesis_stream_name = os.environ['staging_record_stream']
max_retries = int(os.getenv('max_stream_retries', '5'))

s3 = boto3.client('s3')
kinesis = boto3.client('kinesis')

def lambda_handler(event, context):
    failed_messages = []
    failed_records_count = 0
    try:
        for record in event['Records']:
            try:
                message = json.loads(record['body'])
                bucket = message['bucket']
                prefix = message['prefix']
                start_range = 0
                if 'start-range-bytes' in message:
                    start_range = message['start-range-bytes']

                if 'end-range-bytes' in message and message['end-range-bytes'] != -1:
                    end_range = message['end-range-bytes']
                else:
                    end_range = get_object_size(bucket, prefix)

                expression = 'SELECT * FROM S3Object'
                response = s3.select_object_content(
                    Bucket=bucket,
                    Key=prefix,
                    ExpressionType='SQL',
                    Expression=expression,
                    InputSerialization={
                        'CSV': {
                            'FileHeaderInfo': 'USE',
                            'FieldDelimiter': ',',
                            'RecordDelimiter': '\n'
                        }
                    },
                    OutputSerialization={
                        'JSON': {
                            'RecordDelimiter': '\n'
                        }
                    },
                    ScanRange={
                        'Start': start_range,
                        'End': end_range
                    },
                )

                """
                select_object_content() response is an event stream that can be looped to concatenate the overall result set
                Hence, we are joining the results of the stream in a string before converting it to a tuple of dict
                """
                result_stream = []
                for payload in response['Payload']:
                    if records := payload.get('Records'):
                        result_stream.append(records['Payload'].decode('utf-8'))
                failed_records_count = write_kinesis(kinesis_stream_name, ''.join(result_stream).split('\n'))
            except Exception as e:
                failed_messages.append({"itemIdentifier": record['messageId']})
                raise e
    except Exception as e:
        print(e)
        print('Error with event object {}.'.format(json.dumps(event)))
        raise e


    return {
        "statusCode": 200,
        "body": {
            "batchItemFailures": failed_messages,
            "failedStreamingRecordsCount": failed_records_count
        }
    }

def get_object_size(bucket, key):
    end_range = 0
    object_head_response = s3.head_object(Bucket=bucket, Key=key)
    if object_head_response:
        end_range = int(object_head_response['ResponseMetadata']['HTTPHeaders']['content-length'])
    return end_range

def write_kinesis(stream_name, records):
    failed_records_count = 0
    records = to_staging_stream_format(records)

    max_batch_size = 500 #current maximum allowed
    kinesis_batches = [records[x:x + max_batch_size] for x in range(0, len(records), max_batch_size)]

    for kinesis_batch in kinesis_batches:
        kinesis_records = list(map(
            lambda reading:{
                'Data': encode_data(reading),
                'PartitionKey': reading['meter_id']
            }, kinesis_batch))
        failed_records_count = kinesis_put_records(kinesis_records, stream_name)
    return failed_records_count

def encode_data(data):
    return json.dumps(data).encode('utf-8')

def kinesis_put_records(kinesis_records, stream_name, attempt=0):
    result = {}
    try:
        if attempt > max_retries:
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


def to_staging_stream_format(file_records):
    result = []
    for file_record in file_records:
        try:
            json_record = json.loads(file_record)
            unwanted_fields = ['time', 'device_id', 'measure_name']
            measures = {k: v for k, v in json_record.items() if k not in unwanted_fields}
            for measure_name, measure_value in measures.items():
                result.append({
                    'meter_id': json_record['device_id'],
                    'reading_type': measure_name,
                    'reading_value': measure_value,
                    'reading_date_time': json_record['time'][:-3],
                    'reading_source': 'B'
                })
        except Exception as err:
            print('failed to unpack record: ', file_record)
            print("Error:", err)
    return result