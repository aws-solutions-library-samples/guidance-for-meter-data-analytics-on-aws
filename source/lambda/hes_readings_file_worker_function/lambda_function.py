import os
import json
import math
import boto3
from datetime import datetime
bucket = os.environ['BUCKET']
dynamodb_table = os.environ['DYNAMODB_TABLE']
glue_job_name = os.environ['GLUE_JOB_NAME']
region_name = os.environ['REGION_NAME']
timestream_database = os.environ['TIMESTREAM_DATABASE']
timestream_table = os.environ['TIMESTREAM_TABLE']
s3_client = boto3.client('s3')
glue_client = boto3.client('glue')
query_client = boto3.client('timestream-query')
dynamodb_resource = boto3.resource('dynamodb')
dtable = dynamodb_resource.Table(dynamodb_table)
class Query(object):
	def __init__(self, client):
		self.client = client
		self.paginator = client.get_paginator('query')
	def run_query(self, query_string):
		try:
			all_pages = []
			page_iterator = self.paginator.paginate(QueryString=query_string)
			for page in page_iterator:
				all_pages.extend(self._parse_query_result(page))
			return all_pages
		except Exception as e:
			print('Exception while running query:', e)
	def _parse_query_result(self, query_result):
		print(json.dumps(query_result['QueryStatus'], default=str))
		all_rows = []
		for row in query_result['Rows']:
			all_rows.append(self._parse_row(query_result['ColumnInfo'], row))
		return all_rows
	def _parse_row(self, column_info, row):
		row_data = {}
		for j in range(len(row['Data'])):
			row_data.update(self._parse_datum(column_info[j], row['Data'][j]))
		return row_data

	def _parse_datum(self, info, datum):
		if datum.get('NullValue', False):
			return {info['Name']: None}
		if 'ScalarType' in info['Type']: # If the column is of Scalar Type
			return {info['Name']: datum['ScalarValue']}
		else:
			raise Exception('Unhandled column type')
def lambda_handler(event, context):
	try:
		# Parse lambda event
		for record in event['Records']:
			job_detail = {}
			file_request = json.loads(record['body'])
			request_id = file_request['request_id']
			start_date = file_request['requested_payload']['start_date']
			end_date = file_request['requested_payload']['end_date']
			partition_query = ( # nosec
			f'''
			select
				min(time) time_min,
				max(time) time_max,
				count(distinct(time)) partition_count,
				count(time) record_count
			from "{{timestream_database}}"."{{timestream_table}}"
			where time >= '{{start_date}}'
			and time <= '{{end_date}}'
			'''
			) \
			.format(
				timestream_database=timestream_database,
				timestream_table=timestream_table,
				start_date=start_date,
				end_date=end_date
			)
			query = Query(query_client)
			query_output = query.run_query(partition_query)
			time_min = str(query_output[0]['time_min'])
			time_max = str(query_output[0]['time_max'])
			partition_count = int(query_output[0]['partition_count'])
			record_count = int(query_output[0]['record_count'])
			job_detail['record_count'] = record_count
			if record_count > 0:
				worker_cores = 4
				worker_count = math.ceil(partition_count/worker_cores)+1
				#Create string for list of jars in jars folder
				jars_folder = 'assets/glue/jars'
				jars = []
				s3_response = s3_client.list_objects(Bucket=bucket, Prefix=jars_folder)
				for content in s3_response['Contents']:
					if content['Key'][-1:] != '/':
						jars.append(('/'.join(['s3:/',bucket,content['Key']])))
				jars_string = ','.join(jars)
				glue_job_args = {
					'--request_id': request_id,
					'--scriptLocation': 's3://' + bucket + '/assets/glue/scripts/timestream_to_s3.py',
					'--bucket': bucket,
					'--TempDir': 's3://' + bucket + '/temp/',
					'--start_date': time_min,
					'--end_date': time_max,
					'--extra-jars': jars_string,
					'--job-bookmark-option': 'job-bookmark-disable',
					'--timestream_database': timestream_database,
					'--timestream_table': timestream_table,
					'--partition_count': str(partition_count),
					'--dynamodb_table': dynamodb_table,
					'--region': region_name,
					'--enable-spark-ui': 'true',
					'--spark-event-logs-path': 's3://' + bucket + '/logs/sparkHistoryLogs'
				}
				# Start Glue Job
				glue_response = glue_client.start_job_run(
					JobName=glue_job_name,
					Arguments=glue_job_args,
					WorkerType='G.1X',
					NumberOfWorkers=worker_count
				)
				job_detail['run_id'] = glue_response['JobRunId']
				job_detail['args'] = glue_job_args
				status = 'submitted'
			else:
				status = 'skipped'
			# Update DynamoDB record
			dynamodb_response = dtable.update_item(
				Key={'request_id': request_id},
				ExpressionAttributeNames={'#s': 'status'},
				ExpressionAttributeValues={':s': status,':j': job_detail},
				UpdateExpression="SET #s = :s, job_detail = :j"
			)
	except Exception as e:
		print(json.dumps(str(e)))
		dynamodb_response = dtable.update_item(
			Key={'request_id': request_id},
			ExpressionAttributeNames={'#s': 'status'},
			ExpressionAttributeValues={':s': 'failed',':r': str(e)},
			UpdateExpression="SET #s = :s, reason = :r",
		)