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
import os
import urllib.parse

from datetime import datetime

event_bus_name = os.environ['EventBus']
event_bus = boto3.client('events')

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def late_arriving(data_date, now):
    logger.info("checking late arriving event for {}, where as now is {} and difference is {} in minutes"
                .format(data_date, now, (now - data_date).seconds))
    return (now - data_date).total_seconds() / 60 > 60


def to_entry(late_arriver):
    return {
        'Time': late_arriver['event_time'],
        'Source': 'late_arriving_notification',
        'DetailType': 'late_arriving_event',
        'Detail': json.dumps(late_arriver),
        'EventBusName': event_bus_name,
    }


def extract_value(string_with_values, param):
    index_of_param = string_with_values.find(param) + len(param)
    end_of_param = string_with_values.find("/", index_of_param)
    if end_of_param != -1:
        value_to_return = string_with_values[index_of_param + 1: end_of_param]
    else:
        value_to_return = string_with_values[index_of_param + 1:]
    logger.info("returning param {} value {}".format(param, value_to_return))
    return value_to_return


def lambda_handler(event, context):
    now = datetime.now()
    result = {'late_arriving': []}
    try:
        bucket = event['detail']['bucket']['name']
        key = urllib.parse.unquote_plus(event['detail']['object']['key'], encoding='utf-8')
        logger.info("found event for s3://{}/{}".format(bucket, key))

        date_time_str = extract_value(key, "day") + "/" + extract_value(key, "month") + "/" + extract_value(key, "year") \
                        + " " + extract_value(key, "hour")
        logger.info("events added at time {}".format(date_time_str))
        data_date = datetime.strptime(date_time_str, '%d/%m/%Y %H')
        if late_arriving(data_date, now):
            result['late_arriving'].append({
                'bucket': bucket,
                'prefix': key,
                'late_partition_time': data_date.strftime("%m/%d/%Y, %H:%M:%S.%f")[:-3],
                'event_time': now.strftime("%m/%d/%Y, %H:%M:%S.%f")[:-3]
            })

        entries = list(map(lambda r: to_entry(r), result['late_arriving']))
        logger.info("pushing entries {}".format(json.dumps(entries)))

        event_bus_response = {}
        if entries:
            event_bus_response = event_bus.put_events(Entries=entries)

        return {
            "statusCode": 200,
            "body": {
                "result": result,
                "event_bus_response": event_bus_response
            }
        }

    except Exception as e:
        print(e)
        print('Error with event object {}'.format(json.dumps(event)))
        raise e
