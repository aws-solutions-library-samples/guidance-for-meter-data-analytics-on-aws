import os
import json
import uuid
import boto3
from datetime import datetime
# Job Settings
queue_url = os.environ['WORKER_QUEUE_URL']
device_count = int(os.environ['DEVICE_COUNT'])
generation_interval_minutes = int(os.environ['GENERATION_INTERVAL_MINUTES'])
records_per_worker = int(os.environ['RECORDS_PER_WORKER'])
sqs_client = boto3.client('sqs')
def write_sqs(jobs):
	job_log = {'total_readings': 0, 'sqs_messages': 0, 'sqs_api_calls': 0}
	sqs_batch_size = 10
	chunks = [jobs[x:x+sqs_batch_size] for x in range(0, len(jobs), sqs_batch_size)]
	for chunk in chunks:
		job_log['sqs_api_calls'] += 1
		dt = datetime.now().replace(microsecond=0)
		dt_epoch = datetime.now().replace(microsecond=0).timestamp()
		dt_friendly = datetime.now().replace(microsecond=0).isoformat()
		entries = []
		for x in chunk:
			#print('Worker reading generation request for devices ' + str(x['start'] + 1) + ' to ' + str(x['end']) + ' at ' + str(dt_friendly))
			job_log['sqs_messages'] += 1
			job_log['total_readings'] += x['end'] - x['start']
			entry = {
				'Id': '-'.join(['WorkerReadings',str(x['start']),str(x['end']),str(int(dt_epoch))]),
				'MessageBody': json.dumps({
					'RangeStart': x['start'] + 1,
					'RangeEnd': x['end'],
					'TotalDevices': x['end'] - x['start'],
					'BatchId': x['batch_id'],
					'BatchTime': x['batch_time']
				})
			}
			entries.append(entry)
		response = sqs_client.send_message_batch(QueueUrl=queue_url, Entries=entries)
	return(job_log)
def lambda_handler(event, context):
	batch_id = str(uuid.uuid4())
	batch_time = int(datetime.now().timestamp()//(int(generation_interval_minutes) * 60) * (int(generation_interval_minutes) * 60)) * 1000
	job_log = {}
	job_start = datetime.now()
	jobs = []
	for i in range(0, device_count, records_per_worker):
		job = {
			'batch_id': batch_id,
			'batch_time': batch_time,
			'start': i,
			'end': min((i + records_per_worker), device_count)}
		jobs.append(job)
	job_results = write_sqs(jobs)
	job_log.update(job_results)
	job_end = datetime.now()
	job_duration = job_end - job_start
	job_log['batch_id'] = str(batch_id)
	job_log['batch_time'] = batch_time
	job_log['start'] = job_start.replace(microsecond=0).isoformat()
	job_log['end'] = job_end.replace(microsecond=0).isoformat()
	job_log['duration_sec'] = job_duration.total_seconds()
	print(json.dumps(job_log))