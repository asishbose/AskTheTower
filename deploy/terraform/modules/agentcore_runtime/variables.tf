variable "name" {
  type = string
}

variable "region" {
  type = string
}

variable "account_id" {
  type = string
}

variable "image" {
  description = "tower-mcp image URI (ECR, arm64)."
  type        = string
}

variable "ref_client_image" {
  type    = string
  default = ""
}

variable "enable_ref_client" {
  type    = bool
  default = false
}

variable "bedrock_model_id" {
  type    = string
  default = "amazon.nova-micro-v1:0"
}

variable "environment" {
  description = "Tower's environment (services/tower-mcp/README.md). Holds no carrier credential on the Gateway path."
  type        = map(string)
  sensitive   = true
}

variable "table_arns" {
  type = list(string)
}

variable "kms_key_arns" {
  type = list(string)
}

variable "gateway_arn" {
  type = string
}

variable "jwt_discovery_url" {
  type    = string
  default = ""
}

variable "jwt_allowed_audience" {
  type    = list(string)
  default = []
}

variable "jwt_allowed_clients" {
  type    = list(string)
  default = []
}

variable "vpc" {
  description = "Cut-line only: run the Runtime in these private subnets (DirectClient -> internal ALB)."
  type = object({
    subnet_ids         = list(string)
    security_group_ids = list(string)
  })
  default = null
}

variable "log_retention_days" {
  type    = number
  default = 14
}
