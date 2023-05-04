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
import os

import boto3

sqs_client = boto3.client('sqs')
glue_client = boto3.client('glue')


def lambda_handler(event, context):
    jobs = glue_client.get_job_runs(JobName='integrate-meterreadings')

    if any(job["JobRunState"] == "RUNNING" for job in jobs["JobRuns"]):
        print("Running Glue Job detected, return false")
        return {"queue_empty": False}

    queue_name = os.getenv("QUEUE_NAME")
    queue_url = sqs_client.get_queue_url(QueueName=queue_name)['QueueUrl']

    response = sqs_client.get_queue_attributes(QueueUrl=queue_url, AttributeNames=['ApproximateNumberOfMessages',
                                                                                   'ApproximateNumberOfMessagesNotVisible',
                                                                                   'ApproximateNumberOfMessagesDelayed'])

    queue_attr = response["Attributes"]

    num_of_messages = int(queue_attr["ApproximateNumberOfMessages"])
    num_of_messages_not_visible = int(queue_attr["ApproximateNumberOfMessagesNotVisible"])
    num_of_messages_delayed = int(queue_attr["ApproximateNumberOfMessagesDelayed"])

    if num_of_messages + num_of_messages_not_visible + num_of_messages_delayed == 0:
        print(f"Queue [{queue_name}] most likely empty.")
        return {"queue_empty": True}

    return {"queue_empty": False}
