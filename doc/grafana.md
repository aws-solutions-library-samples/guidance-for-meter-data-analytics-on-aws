# Setup of the Data Visualization Using Grafana

## Deployment 



Most of the deployment is done automatically by the `meter-data-analytics` stack, however you still need to configure the following things **before** the deployment.


The `stack-parameter.json` file require an additional parameter to define the authentication provider for Amazon Managed Grafana:
- Allowed values are `AWS_SSO` (preferred) or `SAML`. If you choose `AWS_SSO` your account has to be part of an organization, because it is a requirement in order to use the IAM Identity Center, which is used for SSO. If your account is not part of an organization the deployment will fail. Otherwise if you choose `SAML`, you will need to configure the SAML provider after the deployment (see below).

``` 
    {
      "ParameterKey":"GrafanaDashboardAuthenticationProvider",
      "ParameterValue":"AWS_SSO"
    }
```

## Viewing the Dashboard

In order to view the dashboards after the workspace is created head over to [Amazon Managed Grafana](https://console.aws.amazon.com/grafana). 

1. Select the workspace `AmazonGrafanaWorkspace` created by the AWS CloudFormation stack.

Now you have to configure user access based on the authentication provider you have selected.

### AWS IAM Identity Center

2. Assign a new user or group using the `AWS IAM Identity Center`. For more information, refer to [Managing user and group access to Amazon Managed Grafana](https://docs.aws.amazon.com/grafana/latest/userguide/AMG-manage-users-and-groups-AMG.html).

3. Click on the Grafana workspace URL, sign in, and you are able to view the dashboards, which are stored in the `General` folder.

### SAML using Okta as an IDP

2. A detailed guide of setting up Okta as an IDP for Grafana is provided [here](https://catalog.us-east-1.prod.workshops.aws/workshops/0ee4408e-818a-4774-b03d-bf68bfc016ac/en-US/digital-twin/okta-saml).

3. Click on the Grafana workspace URL, sign in, and you are able to view the dashboards, which are stored in the `General` folder.