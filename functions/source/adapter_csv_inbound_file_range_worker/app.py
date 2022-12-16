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

from kinesis_producer import write_kinesis

kinesis_stream_name = os.environ['staging_record_stream']
max_retries = int(os.getenv('max_stream_retries', '5'))

s3 = boto3.client('s3')

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
                cut_off = ''
                failed_records_count = 0
                for index, payload in enumerate(response['Payload']):
                    if records := payload.get('Records'):
                        staging_records = (cut_off + records['Payload'].decode('utf-8')).split('\n')
                        cut_off = staging_records.pop()
                        if cut_off.endswith('}'):
                            staging_records.append(cut_off)
                            cut_off = ''
                        failed_records_count = failed_records_count \
                                               + write_kinesis(kinesis_stream_name,
                                                               to_staging_stream_format(staging_records),
                                                               max_retries)

            except Exception as e:
                failed_messages.append({"itemIdentifier": record['messageId']})
                raise e
    except Exception as e:
        print(e)
        print('Error with event object {}.'.format(json.dumps(event)))
        raise e

    if failed_records_count == 0:
        return {
            "statusCode": 200,
            "body": {
                "batchItemFailures": failed_messages,
                "failedStreamingRecordsCount": failed_records_count
            }
        }
    else:
        return {
            "statusCode": 500,
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