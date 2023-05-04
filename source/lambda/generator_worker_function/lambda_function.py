import os
import json
import uuid
import boto3
import random
import botocore
from datetime import datetime
late_arrival_minute_offset = int(os.environ['LATE_ARRIVAL_MINUTE_OFFSET'])
late_arrival_percent = int(os.environ['LATE_ARRIVAL_PERCENT'])
late_arrival_simulate = os.environ['LATE_ARRIVAL_SIMULATE']
max_laod = float(os.environ['MAX_LOAD']) #maximum load across all devices
min_load = float(os.environ['MIN_LOAD']) #minimum load across all devices
region_voltage = int(os.environ['REGION_VOLTAGE']) #country-specific reference voltage
timestream_database = os.environ['TIMESTREAM_DATABASE']
timestream_table = os.environ['TIMESTREAM_TABLE']
session = boto3.Session()
write_client = session.client('timestream-write')
write_batch_size = 100
def generate_readings(device_index, reading_time, arrival_time):
	try:
		device_id = str(uuid.uuid3(uuid.NAMESPACE_OID, str(device_index)))
		readings = {'Time': str(reading_time), 'Dimensions': [{'Name': 'device_id', 'Value': device_id, 'DimensionValueType': 'VARCHAR'}], 'MeasureValues': []}
		#create persistent load in range for device based on device_index
		random.seed(device_index) #set seed
		load = int(random.uniform(min_load, max_laod)) # nosec B311
		random.seed(None) #unset seed
		pf = random.uniform(0.8, 0.99) # nosec B311
		ldf = random.uniform(0, 10) # nosec B311
		kw = load * (ldf / 10)
		kva = kw / pf
		vltg = (random.uniform(0, 1) * (round(region_voltage * 1.1, 2) - round(region_voltage * 0.9, 2)) + round(region_voltage * 0.9, 2)) / 1000 # nosec B311
		crrnt = kva / vltg
		readings['MeasureValues'].append({'Name': 'arrival_time', 'Value': arrival_time, 'Type': 'TIMESTAMP'})
		readings['MeasureValues'].append({'Name': 'load', 'Value': str(load), 'Type': 'BIGINT'})
		readings['MeasureValues'].append({'Name': 'pf', 'Value': str(round(pf, 3)), 'Type': 'DOUBLE'})
		readings['MeasureValues'].append({'Name': 'kw', 'Value': str(round(kw, 3)), 'Type': 'DOUBLE'})
		readings['MeasureValues'].append({'Name': 'kva', 'Value': str(round(kva, 3)), 'Type': 'DOUBLE'})
		readings['MeasureValues'].append({'Name': 'vltg', 'Value': str(round(vltg, 3)), 'Type': 'DOUBLE'})
		readings['MeasureValues'].append({'Name': 'crrnt', 'Value': str(round(crrnt, 3)), 'Type': 'DOUBLE'})
		return readings
	except Exception as e:
		raise ValueError(e) from None
def write_records(records, common_attributes):
	try:
		result = write_client.write_records(
			DatabaseName = timestream_database,
			TableName = timestream_table,
			Records = records,
			CommonAttributes = common_attributes
		)
	except botocore.exceptions.ClientError as e:
		raise ValueError(e) from None
def lambda_handler(event, context):
	try:
		# Parse lambda event
		for record in event['Records']:
			item = json.loads(record['body'])
			job_start = datetime.now()
			if late_arrival_simulate == 'ENABLED':
				late_devices = int((item['RangeEnd'] - item['RangeStart'] + 1) * (late_arrival_percent * .01))
			else:
				late_devices = 0
			job_log = {
				'batch_id': item['BatchId'],
				'batch_time': item['BatchTime'],
				'range_start': item['RangeStart'],
				'range_end': item['RangeEnd'],
				'late_devices': late_devices,
				'start': job_start.replace(microsecond=0).isoformat(),
				'late_arrival_percent': late_arrival_percent,
				'records_total': 0,
				'timestream_writes': 0
			} 
			# Generate records for given range and write in batches to Timestream
			for i in range(item['RangeStart'], item['RangeEnd'] + 1, write_batch_size):
				records = []
				for device_index in range(i, min(i + write_batch_size - 1, item['RangeEnd']) + 1):
					common_attributes = {'MeasureName': 'readings', 'MeasureValueType': 'MULTI'}
					if device_index <= late_devices:
						reading_time = str(int(item['BatchTime']) - int(late_arrival_minute_offset * 60 * 1000))
					else:
						reading_time = str(item['BatchTime'])
					record = generate_readings(device_index=device_index, reading_time=reading_time, arrival_time=str(item['BatchTime']))
					job_log['records_total'] += 1
					records.append(record)
				write_records(records, common_attributes)
				job_log['timestream_writes'] += 1
			# Job Logging
			job_end = datetime.now()
			job_log['end'] = job_end.replace(microsecond=0).isoformat()
			job_duration = job_end - job_start
			job_log['duration_sec'] = (job_duration).total_seconds()
			job_log['records_avg_per_sec'] = float('{:.2f}'.format(job_log['records_total']/job_duration.total_seconds()))
			print(json.dumps(job_log))
	except ValueError as e:
		print(json.dumps(str(e)))