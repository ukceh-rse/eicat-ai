# Terraform Deployment
The EICAT-AI application can be deployed to AWS using Terraform. To do so follow the latest installation instructions to install Terraform, install the AWS CLI and configure with appropriate access key and credentials. 
## IAM Roles
You must ensure that your IAM role has been configured with the following roles to allow Terraform to handle the full deployment:
- AWSBedrock
- AppRunner
## Setup
First initialize terraform in the `terraform/` directory:
```shell
terraform init
```
You can edit your configuration by editing the variables define in `terraform/terraform.tfvars`
## Apply
You can apply you configuration using:
```shell
terraform apply
```
This will deploy the setup using your AWS configuration and will return the deployment URL which you can use for testing.
