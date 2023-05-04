import os
import json
import boto3
import cfnresponse
import botocore.exceptions
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization as crypto_serialization
from cryptography.hazmat.backends import default_backend as crypto_default_backend
sm_client = boto3.client('secretsmanager')
def generate_key_pair():
	try:
		key = rsa.generate_private_key(
			backend=crypto_default_backend(),
			public_exponent=65537,
			key_size=2048
		)
		private_key = key.private_bytes(
			crypto_serialization.Encoding.PEM,
			crypto_serialization.PrivateFormat.TraditionalOpenSSL,
			crypto_serialization.NoEncryption()
		).decode('utf-8')
		public_key = key.public_key().public_bytes(
			crypto_serialization.Encoding.OpenSSH,
			crypto_serialization.PublicFormat.OpenSSH
		).decode('utf-8')
		return {'private': private_key, 'public': public_key}
	except Exception as e:
		raise ValueError(e)
def create_secret(secret_name, secret_string):
	try:
		response = sm_client.create_secret(Name = secret_name, SecretString = secret_string)
		return {'Result': 'secret successfully created', 'SecretARN': response['ARN'], 'SecretName': response['Name']}
	except botocore.exceptions.ClientError as error:
		if error.response['Error']['Code'] == 'ResourceExistsException':
			response = describe_secret(secret_name)
			raise ValueError({'Result': error.response['Message']})
		else:
			raise ValueError({'Result': error.response['Message']})
def delete_secret(secret_name):
	try:
		response = sm_client.delete_secret(SecretId = secret_name, ForceDeleteWithoutRecovery = True)
		return {'Result': 'secret successfully deleted', 'SecretARN': response['ARN'], 'SecretName': response['Name']}
	except botocore.exceptions.ClientError as error:
		raise ValueError({'Result': error.response['Message']})
def describe_secret(secret_name):
	try:
		response = sm_client.describe_secret(SecretId = secret_name)
		return response
	except botocore.exceptions.ClientError as error:
		raise ValueError({'Result': error.response['Message']})
def lambda_handler(event, context):
	try:
		secret_name = ('/').join([(event['StackId'].split('/')[1]),'sftp','private_key'])
		if event['RequestType'] == 'Create':
			keys = generate_key_pair()
			responseData = create_secret(secret_name, keys['private'])
			responseData['PublicKey'] = keys['public']
			cfnresponse.send(event, context, cfnresponse.SUCCESS, responseData)
		elif event['RequestType'] == 'Delete':
			responseData = delete_secret(secret_name)
			cfnresponse.send(event, context, cfnresponse.SUCCESS, responseData)
	except ValueError as error:
		responseData = {'Result': error.response['Message']}
		cfnresponse.send(event, context, cfnresponse.FAILED, responseData)
	except Exception as error:
		responseData = {'Result': str(error)}
		cfnresponse.send(event, context, cfnresponse.FAILED, responseData)