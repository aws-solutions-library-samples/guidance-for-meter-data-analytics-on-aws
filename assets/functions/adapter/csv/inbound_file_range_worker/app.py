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

kinesis_stream_name = destination_queue = os.environ['TargetKinesisDataStream']

s3 = boto3.client('s3')
kinesis = boto3.client('kinesis')

def lambda_handler(event, context):
    failed_messages = []
    for record in event['Records']:
        bucket = record["bucket"]
        key = record["key"]
        start_range = 0
        if "start-range-bytes" in record:
            start_range = record["start-range-bytes"]

        if "end-range-bytes" in record and record["end-range-bytes"] != -1:
            end_range = record["end-range-bytes"]
        else:
            end_range = get_object_size(bucket, key)
        try:
            expression = 'SELECT * FROM S3Object'
            response = s3.select_object_content(
                Bucket=bucket,
                Key=key,
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
                        'RecordDelimiter': ','
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
            for event in response['Payload']:
                if records := event.get('Records'):
                    result_stream.append(records['Payload'].decode('utf-8'))

            write_kinesis(kinesis_stream_name, result_stream)
        except Exception as e:
            print(e)
            print('Error with event object {} from bucket {}.'.format(key, bucket))
            failed_messages.append({"itemIdentifier": record["messageId"]})


    return {
        "statusCode": 200,
        "body": {
            "batchItemFailures": failed_messages
        }
    }

def get_object_size(bucket, key):
    end_range = 0
    object_head_response = s3.head_object(Bucket=bucket, Key=key)
    if object_head_response:
        end_range = int(object_head_response['ResponseMetadata']['HTTPHeaders']['content-length'])
    return end_range

def write_kinesis(stream_name, records):
    max_batch_size = 500 #current maximum allowed
    kinesis_batches = [records[x:x + max_batch_size] for x in range(0, len(records), max_batch_size)]

    for kinesis_batch in kinesis_batches:
        kinesis_records = []
        for reading in kinesis_batch:
            kinesis_records.append({
                'Data': json.dumps(reading),
                'PartitionKey': reading["DeviceID"]
            })
        try:
            result = kinesis.put_records(
                StreamName=stream_name,
                Records=kinesis_records, )

            status = result['ResponseMetadata']['HTTPStatusCode']
            print("Processed %d records. WriteRecords Status: %s" %
                  (len(kinesis_records), status))
        except Exception as err:
            print("Error:", err)
            if result is not None:
                print("Result:{}".format(result))
