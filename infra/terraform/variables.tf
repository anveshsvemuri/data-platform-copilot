variable "aws_region" {
  description = "AWS region for the deployment."
  type        = string
  default     = "us-east-1"
}

variable "name_prefix" {
  description = "Prefix applied to deployment resources."
  type        = string
  default     = "data-platform-copilot"
}

variable "vpc_id" {
  description = "Existing VPC for the load balancer and ECS service."
  type        = string
}

variable "public_subnet_ids" {
  description = "At least two public subnets in different availability zones."
  type        = list(string)

  validation {
    condition     = length(var.public_subnet_ids) >= 2
    error_message = "Provide at least two public subnet IDs."
  }
}

variable "allowed_cidr_blocks" {
  description = "Trusted client CIDRs allowed to reach the MCP load balancer."
  type        = list(string)

  validation {
    condition     = length(var.allowed_cidr_blocks) > 0 && !contains(var.allowed_cidr_blocks, "0.0.0.0/0")
    error_message = "Provide trusted CIDRs; unrestricted public access is intentionally rejected."
  }
}

variable "image_digest" {
  description = "Immutable sha256 digest pushed to the module-created ECR repository."
  type        = string

  validation {
    condition     = can(regex("^sha256:[0-9a-f]{64}$", var.image_digest))
    error_message = "image_digest must be a sha256 digest, not a mutable tag."
  }
}

variable "mcp_token_secret_arn" {
  description = "ARN of an existing Secrets Manager secret containing the MCP bearer token."
  type        = string
  sensitive   = true
}

variable "certificate_arn" {
  description = "ACM certificate ARN for mandatory HTTPS."
  type        = string
}

variable "desired_count" {
  description = "Number of stateless MCP tasks."
  type        = number
  default     = 1
}

variable "log_retention_days" {
  description = "CloudWatch log retention period."
  type        = number
  default     = 14
}

variable "environment" {
  description = "Environment dimension used by copilot observability metrics."
  type        = string
  default     = "demo"
}

variable "alarm_actions" {
  description = "Optional SNS topic ARNs or incident actions invoked by copilot alarms."
  type        = list(string)
  default     = []
}
