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


import json
import boto3
import requests
import cfnresponse
import string
import random
import os

grafana = boto3.client('grafana')
s3_key_prefix = os.environ['S3KeyPrefix']
region = str(os.environ['AWS_REGION'])
s3 = boto3.resource('s3')
secrects_manager = boto3.client('secretsmanager')
secret_name = 'grafana-api-key'


# Creates an Grafana API key and automatically creates the dashboards
def lambda_handler(event, context):
    if event["RequestType"] == "Delete":
        cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
        return {
            'statusCode': 200,
            'body': "success"
        }

    grafana_id = event["ResourceProperties"]["grafanaId"]
    bucket = event["ResourceProperties"]["bucket"]
    athena_workgroup = event["ResourceProperties"]["workgroup"]
    grafana_workspace_url = "https://" + str(grafana_id) + ".grafana-workspace." + region + ".amazonaws.com"
    data_path = f"{s3_key_prefix}assets/grafana/"

    # create API key
    key_name = 'Admin-' + ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5))
    response = grafana.create_workspace_api_key(keyName=key_name, keyRole='ADMIN', secondsToLive=4000,
                                                workspaceId=str(grafana_id))

    api_key = response["key"]

    try:
        secrects_manager.update_secret(SecretId=secret_name, SecretString=api_key)
    except:
        secrects_manager.create_secret(Name=secret_name, SecretString=api_key)

    header = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": "Bearer " + api_key
    }

    # add Athena as a datasource to grafana

    datasource_id = prepare_n_deploy_datasource(data_path, 'athena-data-source.json', s3, region, bucket,
                                                athena_workgroup, grafana_workspace_url, header)

    weather_db = prepare_dashboard(data_path, 'weather.json', s3, datasource_id, bucket)
    outage_map_db = prepare_dashboard(data_path, 'outage-map.json', s3, datasource_id, bucket)
    anomaly_dip_n_spike_db = prepare_dashboard(data_path, 'anomaly-dip-n-spike.json', s3, datasource_id, bucket)
    forecast_db = prepare_dashboard(data_path, 'forecast.json', s3, datasource_id, bucket)

    deploy_dashboard(grafana_workspace_url, header, weather_db)
    deploy_dashboard(grafana_workspace_url, header, outage_map_db)
    deploy_dashboard(grafana_workspace_url, header, anomaly_dip_n_spike_db)
    deploy_dashboard(grafana_workspace_url, header, forecast_db)

    cfnresponse.send(event, context, cfnresponse.SUCCESS, {})

    return {
        'statusCode': 200,
        'body': "success"
    }


def prepare_n_deploy_datasource(data_path, datasource_name, client, region, bucket, athena_workgroup, workspace_url,
                                header):
    key = data_path + datasource_name
    obj = client.Object(bucket, key)
    data = obj.get()['Body'].read().decode('utf-8')
    ds = json.loads(data)

    if 'workgroup' in ds['jsonData']:
        ds['jsonData']['workgroup'] = athena_workgroup
    if 'region' in ds['jsonData']:
        ds['jsonData']['defaultRegion'] = region

    requests.post(
        url=workspace_url + "/api/datasources",
        headers=header,
        data=json.dumps(ds),
        verify=True)

    r = requests.get(
        url=workspace_url + "/api/datasources",
        headers=header,
        verify=True)

    datasource_id = r.json()[0]['uid']
    return datasource_id


def prepare_dashboard(data_path, dashboard_name, client, datasource_id, bucket):
    key = data_path + dashboard_name
    obj = client.Object(bucket, key)
    data = obj.get()['Body'].read().decode('utf-8')
    db = json.loads(data)

    for panel in db['dashboard']['panels']:
        if 'datasource' in panel:
            panel['datasource']['uid'] = datasource_id
            for target in panel['targets']:
                if 'datasource' in target:
                    target['datasource']['uid'] = datasource_id

    for item in db['dashboard']['templating']['list']:
        if 'datasource' in item:
            item['datasource']['uid'] = datasource_id

    return db


def deploy_dashboard(workspace_url, header, dashboard):
    r = requests.post(
        url=workspace_url + '/api/dashboards/db',
        headers=header,
        data=json.dumps(dashboard),
        verify=True)
