import os
import json
import boto3
import awswrangler as wr
from datetime import datetime
timestream_db = os.environ['TIMESTREAM_DATABASE']
timestream_table = os.environ['TIMESTREAM_TABLE']
client = boto3.client('timestream-query')
def test_date(field, date):
	date_formats = ['%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S.%f000', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M']
	for date_format in date_formats:
		try:
			return datetime.strptime(date, date_format)
		except ValueError:
			pass
	raise ValueError(f'Invalid date format of {date} for field {field}')
def query(date_start, offset_start, offset_end):
	try:
		query_string = ( # nosec
		f'''
		select
			offset, time, arrival_time, device_id, measure_name, load, crrnt, pf, kva, kw, vltg
		from (
			select
				row_number() over (order by time asc, device_id asc) offset,
				time, arrival_time, device_id, measure_name, load, crrnt, pf, kva, kw, vltg
			from "{{database}}"."{{table}}"
			where time >= '{{date_start}}'
		)
		where offset > {{offset_start}}
		and offset <= {{offset_end}}
		order by offset asc
		'''
		) \
		.format(
			database=timestream_db,
			table=timestream_table,
			offset_start=offset_start,
			offset_end=offset_end,
			date_start=date_start
		)
		df = wr.timestream.query(query_string)
		df['time'] = df['time'].dt.strftime('%Y-%m-%d %H:%M:%S.%f')
		df['arrival_time'] = df['arrival_time'].dt.strftime('%Y-%m-%d %H:%M:%S.%f')
		return df
	except Exception as e:
		print(e)
		return None
def lambda_handler(event, context):
	try:
		job_start = datetime.now()
		job_log = {'start': job_start.replace(microsecond=0).isoformat(), 'records_total': 0}
		params = event['queryStringParameters']
		if 'start_date' in params:
			formatted_date = test_date('start_date', params['start_date'])
			params.update({'start_date': formatted_date.strftime('%Y-%m-%d %H:%M:%S.%f')})
		else:
			raise ValueError(f'start_date is a required field')
		if 'offset' in params:
			params.update({'offset': int(params['offset'])})
		else:
			params.update({'offset': 0})
		if 'page_size' in params:
			params.update({'page_size': int(params['page_size'])})
		else:
			params.update({'page_size': 10})
		results = query(params['start_date'], params['offset'], params['offset'] + params['page_size'])          
		payload = {
			'filter_params': {'start_date': params['start_date'],'offset': params['offset']},
			'results': {'records_total': job_log['records_total']},
			'records': []
		}
		if results is not None:
			records = results.to_dict(orient='records')
			job_log['records_total'] += len(records)
			last_record = records[-1]
			payload['results'].update({'records_total': job_log['records_total']})
			payload['results'].update({'last_date': last_record['time']})
			payload['results'].update({'last_offset': last_record['offset']})
			payload['records'] =records
		# Job Logging
		job_end = datetime.now()
		job_log['end'] = job_end.replace(microsecond=0).isoformat()
		job_duration = job_end - job_start
		job_log['duration_sec'] = (job_duration).total_seconds()
		job_log['records_avg_per_sec'] = float('{:.2f}'.format(job_log['records_total']/job_duration.total_seconds()))
		print(json.dumps(job_log))
		return {
			'statusCode': 200,
			'headers': {'Content-Type': 'application/json'},
			'body': json.dumps(payload)
		}
	except Exception as e:
		print(json.dumps({'error': str(e)}))
		return {
			'statusCode': 500,
			'headers': {'Content-Type': 'application/json'},
			'body': json.dumps({'error': str(e)})
		}