terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Variables
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "app_name" {
  description = "Application name"
  type        = string
  default     = "eicat-ai"
}

variable "github_repo_url" {
  description = "GitHub repository URL"
  type        = string
  default     = "https://github.com/YOUR_USERNAME/eicat-ai"
}

variable "deploy_branch" {
  description = "Git branch to deploy"
  type        = string
  default     = "main"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

# Create GitHub connection for private repository access
resource "aws_apprunner_connection" "github" {
  connection_name = "${var.app_name}-github-connection"
  provider_type   = "GITHUB"

  tags = {
    Name        = "${var.app_name} GitHub Connection"
    Environment = var.environment
  }
}

# IAM role for App Runner
resource "aws_iam_role" "apprunner_instance_role" {
  name = "${var.app_name}-apprunner-instance-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "tasks.apprunner.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.app_name} App Runner Role"
    Environment = var.environment
  }
}

# App Runner service
resource "aws_apprunner_service" "eicat_ai" {
  service_name = var.app_name

  source_configuration {
    auto_deployments_enabled = true
    
    code_repository {
      repository_url = var.github_repo_url
      
      code_configuration {
        configuration_source = "REPOSITORY"
      }
      
      source_code_version {
        type  = "BRANCH"
        value = var.deploy_branch
      }
    }
  }

  instance_configuration {
    cpu               = "0.25 vCPU"
    memory            = "0.5 GB"
    instance_role_arn = aws_iam_role.apprunner_instance_role.arn
  }

  health_check_configuration {
    healthy_threshold   = 1
    interval            = 10
    path                = "/health"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 5
  }

  tags = {
    Name        = var.app_name
    Environment = var.environment
  }

  depends_on = [aws_apprunner_connection.github]
}

# Outputs
output "app_url" {
  description = "App Runner service URL"
  value       = "https://${aws_apprunner_service.eicat_ai.service_url}"
}

output "connection_arn" {
  description = "GitHub connection ARN"
  value       = aws_apprunner_connection.github.arn
}

output "connection_status" {
  description = "GitHub connection status"
  value       = aws_apprunner_connection.github.status
}

output "service_id" {
  description = "App Runner service ID"
  value       = aws_apprunner_service.eicat_ai.service_id
}