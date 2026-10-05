#!/bin/bash
# Infrastructure Provisioning and Deployment Script for Cloud Run & Secret Manager

set -e

echo "Initializing Terraform Infrastructure Provisioning..."
terraform init

echo "Validating Terraform Configuration..."
terraform validate

echo "Applying Infrastructure Configuration..."
terraform apply -auto-approve

echo "Infrastructure deployment and Secret Manager binding completed successfully."
