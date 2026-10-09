# Tower on Bedrock AgentCore Runtime (10 §1-2): the container from services/tower-mcp, MCP over Streamable HTTP on
# 0.0.0.0:8000/mcp (the image's default), stateless. Optionally the reference client as a second Runtime agent
# (the Strands-on-Bedrock showcase).
#
# Inbound auth per spike A (RUN-ALL Decisions): a bearer JWT validated by Runtime's custom JWT authorizer
# (discovery URL of the issuer) and again by Tower itself (TOWER_JWKS_URL, user_id = sub); the Authorization
# header is allow-listed through to the container for that. Without a discovery URL Runtime falls back to IAM
# (SigV4) inbound auth — fine for the reference client, not for Alexa+.

locals {
  runtime_name = "${replace(var.name, "-", "_")}_tower"
  log_group    = "/aws/bedrock-agentcore/runtimes/${aws_bedrockagentcore_agent_runtime.tower.agent_runtime_id}-DEFAULT"
  index_arns   = [for a in var.table_arns : "${a}/index/*"]
}

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["bedrock-agentcore.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [var.account_id]
    }
  }
}

resource "aws_iam_role" "runtime" {
  name               = "${var.name}-agentcore-runtime"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

data "aws_iam_policy_document" "runtime" {
  statement {
    sid       = "EcrAuth"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    sid       = "EcrPull"
    actions   = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"]
    resources = ["arn:aws:ecr:${var.region}:${var.account_id}:repository/${var.name}/*"]
  }
  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams", "logs:DescribeLogGroups"]
    resources = ["arn:aws:logs:${var.region}:${var.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*", "arn:aws:logs:${var.region}:${var.account_id}:log-group:aws/spans:*"]
  }
  statement {
    sid       = "Traces"
    actions   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords", "xray:GetSamplingRules", "xray:GetSamplingTargets"]
    resources = ["*"]
  }
  statement {
    sid       = "Metrics"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["bedrock-agentcore", "AskTheTower"]
    }
  }
  statement {
    sid = "ConsentStore"
    actions = [
      "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:Query",
      "dynamodb:ConditionCheckItem", "dynamodb:TransactWriteItems", "dynamodb:BatchGetItem",
    ]
    resources = concat(var.table_arns, local.index_arns)
  }
  statement {
    sid       = "Keys"
    actions   = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey", "kms:GenerateMac", "kms:VerifyMac", "kms:DescribeKey"]
    resources = var.kms_key_arns
  }
  statement {
    sid       = "CarrierGateway"
    actions   = ["bedrock-agentcore:InvokeGateway"]
    resources = [var.gateway_arn]
  }
  statement {
    sid = "WorkloadIdentity"
    actions = [
      "bedrock-agentcore:GetWorkloadAccessToken",
      "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
      "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
    ]
    resources = [
      "arn:aws:bedrock-agentcore:${var.region}:${var.account_id}:workload-identity-directory/default",
      "arn:aws:bedrock-agentcore:${var.region}:${var.account_id}:workload-identity-directory/default/workload-identity/*",
    ]
  }
  dynamic "statement" {
    for_each = var.enable_ref_client ? [1] : []
    content {
      sid       = "RefClientModel"
      actions   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream", "bedrock:Converse", "bedrock:ConverseStream"]
      resources = ["arn:aws:bedrock:${var.region}::foundation-model/*", "arn:aws:bedrock:*:${var.account_id}:inference-profile/*"]
    }
  }
}

resource "aws_iam_role_policy" "runtime" {
  name   = "tower"
  role   = aws_iam_role.runtime.id
  policy = data.aws_iam_policy_document.runtime.json
}

resource "aws_bedrockagentcore_agent_runtime" "tower" {
  agent_runtime_name    = local.runtime_name
  description           = "Ask the Tower MCP server (line_is_ok, is_reachable, watch_line)"
  role_arn              = aws_iam_role.runtime.arn
  environment_variables = var.environment

  agent_runtime_artifact {
    container_configuration {
      container_uri = var.image
    }
  }

  network_configuration {
    network_mode = var.vpc == null ? "PUBLIC" : "VPC"
    dynamic "network_mode_config" {
      for_each = var.vpc == null ? [] : [var.vpc]
      content {
        subnets         = network_mode_config.value.subnet_ids
        security_groups = network_mode_config.value.security_group_ids
      }
    }
  }

  protocol_configuration {
    server_protocol = "MCP"
  }

  dynamic "authorizer_configuration" {
    for_each = var.jwt_discovery_url == "" ? [] : [1]
    content {
      custom_jwt_authorizer {
        discovery_url    = var.jwt_discovery_url
        allowed_audience = length(var.jwt_allowed_audience) > 0 ? var.jwt_allowed_audience : null
        allowed_clients  = length(var.jwt_allowed_clients) > 0 ? var.jwt_allowed_clients : null
      }
    }
  }

  request_header_configuration {
    request_header_allowlist = ["Authorization"]
  }

  depends_on = [aws_iam_role_policy.runtime]
}

resource "aws_cloudwatch_log_group" "tower" {
  # Runtime writes here; created up front so retention applies and `make down` removes it.
  name              = local.log_group
  retention_in_days = var.log_retention_days
}

# --- optional: the reference client as a second Runtime agent ---------------------------------------------------

resource "aws_bedrockagentcore_agent_runtime" "ref_client" {
  count = var.enable_ref_client ? 1 : 0

  agent_runtime_name = "${replace(var.name, "-", "_")}_ref_client"
  description        = "Reference client (Strands on Bedrock) calling Tower over MCP"
  role_arn           = aws_iam_role.runtime.arn
  environment_variables = {
    BEDROCK_MODEL_ID = var.bedrock_model_id
    TOWER_MCP_URL    = "https://bedrock-agentcore.${var.region}.amazonaws.com/runtimes/${urlencode(aws_bedrockagentcore_agent_runtime.tower.agent_runtime_arn)}/invocations?qualifier=DEFAULT"
  }

  agent_runtime_artifact {
    container_configuration {
      container_uri = var.ref_client_image
    }
  }

  network_configuration {
    network_mode = "PUBLIC"
  }

  protocol_configuration {
    server_protocol = "HTTP"
  }

  depends_on = [aws_iam_role_policy.runtime]
}
