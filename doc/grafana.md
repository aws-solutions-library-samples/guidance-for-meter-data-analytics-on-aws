# Setup of the Data Visualization using Grafana

## Deployment

The `meter-data-analytics` stack automatically sets up the following:

- The Amazon Managed Grafana Workspace.
- A Lambda function ``, that imports the dashboards in S3 to Grafana.

## Viewing the Dashboard

In order to view the dashboards after the workspace is created head over to [Amazon Managed Grafana](https://console.aws.amazon.com/grafana). 

1. Select the workspace `AmazonGrafanaWorkspace` created by the Cloudformation stack.
2. Assign a new user or group using the `AWS IAM Identity Center`. For more information, refer to [Managing user and group access to Amazon Managed Grafana](https://docs.aws.amazon.com/grafana/latest/userguide/AMG-manage-users-and-groups-AMG.html).

3. Click on the Grafana workspace URL, sign in and you should be able to view the dashboards, which are stored in the `General` folder.
