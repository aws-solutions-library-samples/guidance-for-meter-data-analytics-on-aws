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

# Creates an Grafana API key and automatically creates the dashboards
def lambda_handler(event, context):
    
    if event["RequestType"] == "Delete":
        cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
        return {
            'statusCode': 200,
            'body': "success"
        }
   
    client = boto3.client('grafana')
    grafana_id = event["ResourceProperties"]["grafanaId"]
    bucket = event["ResourceProperties"]["bucket"]
    athena_workgroup = event["ResourceProperties"]["workgroup"]
    grafana_workspace = "https://" + str(grafana_id) + ".grafana-workspace.us-east-1.amazonaws.com"
    data_path = "artefacts/assets/grafana/"
    # create API key
    key_name = 'Admin-' + ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5))
    response = client.create_workspace_api_key(keyName=key_name, keyRole='ADMIN', secondsToLive=4000, workspaceId=str(grafana_id))
 
    api_key = response["key"]

    header = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": "Bearer " + api_key
    }

    # add Athena as a datasource to grafana
    api_path = "/api/datasources"
    s3 = boto3.resource('s3')

    key = data_path + "athena-data-source.json"
    obj = s3.Object(bucket, key)
    data = obj.get()['Body'].read().decode('utf-8')
    ds = json.loads(data)

    ds['jsonData']['workgroup'] = athena_workgroup

    r = requests.post(
        url = grafana_workspace+api_path, 
        headers = header, 
        data = json.dumps(ds), 
        verify=True)

    r = requests.get(
            url = grafana_workspace+api_path, 
            headers = header, 
            verify=True)
    # assuming only one datasource exists
    datasource_id = r.json()[0]['uid']
    
    api_path = "/api/dashboards/db"

    # deploy weather dashboard
    key = data_path + "weather.json"
    obj = s3.Object(bucket, key)
    data = obj.get()['Body'].read().decode('utf-8')
    db = json.loads(data)
    for i in range(len(db['dashboard']['panels'])):
        db['dashboard']['panels'][i]['datasource']['uid'] = datasource_id
        for j in range(len(db['dashboard']['panels'][i]['targets'])):
            if 'datasource' in db['dashboard']['panels'][i]['targets'][j]:
                db['dashboard']['panels'][i]['targets'][j]['datasource']['uid'] = datasource_id

    for i in range(len(db['dashboard']['templating']['list'])):
        if 'datasource' in db['dashboard']['templating']['list'][i]:
            db['dashboard']['templating']['list'][i]['datasource']['uid'] = datasource_id
    
    r = requests.post(
        url = grafana_workspace+api_path, 
        headers = header, 
        data = json.dumps(db), 
        verify=True)  
    
    # deploy outage map dashboard
    key = data_path + "outage-map.json"
    obj = s3.Object(bucket, key)
    data = obj.get()['Body'].read().decode('utf-8')
    db = json.loads(data)
    
    for i in range(len(db['dashboard']['panels'])):
        db['dashboard']['panels'][i]['datasource']['uid'] = datasource_id
        for j in range(len(db['dashboard']['panels'][i]['targets'])):
            if 'datasource' in db['dashboard']['panels'][i]['targets'][j]:
                db['dashboard']['panels'][i]['targets'][j]['datasource']['uid'] = datasource_id
    
    for i in range(len(db['dashboard']['templating']['list'])):
        if 'datasource' in db['dashboard']['templating']['list'][i]:
            db['dashboard']['templating']['list'][i]['datasource']['uid'] = datasource_id

    r = requests.post(
        url = grafana_workspace+api_path, 
        headers = header, 
        data = json.dumps(db), 
        verify=True)
    
    # deploy anomaly spike and dip dashboard
    key = data_path + "anomaly-dip-n-spike.json"
    obj = s3.Object(bucket, key)
    data = obj.get()['Body'].read().decode('utf-8')
    db = json.loads(data)
    
    for i in range(len(db['dashboard']['panels'])):
        db['dashboard']['panels'][i]['datasource']['uid'] = datasource_id
        for j in range(len(db['dashboard']['panels'][i]['targets'])):
            if 'datasource' in db['dashboard']['panels'][i]['targets'][j]:
                db['dashboard']['panels'][i]['targets'][j]['datasource']['uid'] = datasource_id

    for i in range(len(db['dashboard']['templating']['list'])):
        if 'datasource' in db['dashboard']['templating']['list'][i]:
            db['dashboard']['templating']['list'][i]['datasource']['uid'] = datasource_id

    r = requests.post(
        url = grafana_workspace+api_path, 
        headers = header, 
        data = json.dumps(db), 
        verify=True)
    
    # deploy forecast dashboard
    key = data_path + "forecast.json"
    obj = s3.Object(bucket, key)
    data = obj.get()['Body'].read().decode('utf-8')
    db = json.loads(data)
    
    for i in range(len(db['dashboard']['panels'])):
        db['dashboard']['panels'][i]['datasource']['uid'] = datasource_id
        for j in range(len(db['dashboard']['panels'][i]['targets'])):
            if 'datasource' in db['dashboard']['panels'][i]['targets'][j]:
                db['dashboard']['panels'][i]['targets'][j]['datasource']['uid'] = datasource_id

    for i in range(len(db['dashboard']['templating']['list'])):
        if 'datasource' in db['dashboard']['templating']['list'][i]:
            db['dashboard']['templating']['list'][i]['datasource']['uid'] = datasource_id

    r = requests.post(
        url = grafana_workspace+api_path, 
        headers = header, 
        data = json.dumps(db), 
        verify=True)
    

    cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
    return {
        'statusCode': 200,
        'body': "success"
    }
