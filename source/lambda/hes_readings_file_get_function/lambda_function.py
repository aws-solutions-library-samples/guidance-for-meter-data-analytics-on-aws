import os
import json
import boto3
import decimal
from boto3.dynamodb.conditions import Key, Attr
dynamodb_table = os.environ['DYNAMODB_TABLE']
dynamodb_resource = boto3.resource('dynamodb')
dtable = dynamodb_resource.Table(dynamodb_table)
class DecimalEncoder(json.JSONEncoder):
	def default(self, o):
		if isinstance(o, decimal.Decimal):
			return str(o)
		if isinstance(o, set):
			return list(o)
		return super(DecimalEncoder, self).default(o)
def lambda_handler(event, context):
	try:
		params = event['queryStringParameters']
		if 'request_id' not in params:
			raise ValueError(f'request_id is a required field')
		else:
			request_id = event['queryStringParameters']['request_id']
			payload = {'request_id': request_id}

		dynamodb_response = dtable.query(KeyConditionExpression=Key('request_id').eq(request_id))
		item = dynamodb_response['Items'][0]

		# Add status and sftp_location from item
		payload['status'] = item['status']
		if 'sftp_location' in item:
			payload['sftp_location'] = item['sftp_location']
		if 'job_detail' in item:
			if 'record_count' in item['job_detail']:
				payload['record_count'] = int(item['job_detail']['record_count'])
		return {
			'statusCode': 200,
			'headers': {'Content-Type': 'application/json'},
			'body': json.dumps(payload,cls=DecimalEncoder)
		}
	except Exception as e:
		print(json.dumps({'error': str(e)}))
		return {
			'statusCode': 500,
			'headers': {'Content-Type': 'application/json'},
			'body': json.dumps({'error': str(e)})
		}