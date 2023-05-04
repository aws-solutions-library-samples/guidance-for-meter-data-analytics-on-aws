import os
import json
import uuid
import boto3
queue_url = os.environ['SQS_QUEUE_URL']
dynamodb_table = os.environ['DYNAMODB_TABLE']
sqs_client = boto3.client('sqs')
dynamodb_resource = boto3.resource('dynamodb')
dtable = dynamodb_resource.Table(dynamodb_table)
def lambda_handler(event, context):
	try:
		event_body = json.loads(event['body'])
		# Validate event body
		if 'start_date' not in event_body:
			raise ValueError(f'start_date is a required field')
		if 'end_date' not in event_body:
			raise ValueError(f'end_date is a required field')
		file_request = {
			'request_id': event['requestContext']['requestId'],
			'requested_payload': {'start_date': event_body['start_date'], 'end_date': event_body['end_date']}
		}
		response = sqs_client.send_message(QueueUrl=queue_url, MessageBody=json.dumps(file_request)) # Add request to queue
		file_request.update({'status': 'queued'}) # Log request to DynamoDB
		dynamodb_response = dtable.put_item(Item=file_request)
		return {
			'statusCode': 200,
			'headers': {'Content-Type': 'application/json'},
			'body': json.dumps({'request_id': event['requestContext']['requestId'], 'status': 'queued'})
		}
	except Exception as e:
		print(json.dumps({'error': str(e)}))
		return {
			'statusCode': 500,
			'headers': {'Content-Type': 'application/json'},
			'body': json.dumps({'status': 'failed', 'error': str(e)})
		}