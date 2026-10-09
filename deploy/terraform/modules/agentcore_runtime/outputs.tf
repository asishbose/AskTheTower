output "runtime_arn" {
  value = aws_bedrockagentcore_agent_runtime.tower.agent_runtime_arn
}

output "runtime_id" {
  value = aws_bedrockagentcore_agent_runtime.tower.agent_runtime_id
}

output "role_arn" {
  value = aws_iam_role.runtime.arn
}

output "invoke_url" {
  description = "MCP endpoint: the Runtime invocation URL for the DEFAULT endpoint."
  value       = "https://bedrock-agentcore.${var.region}.amazonaws.com/runtimes/${urlencode(aws_bedrockagentcore_agent_runtime.tower.agent_runtime_arn)}/invocations?qualifier=DEFAULT"
}

output "log_group_name" {
  value = aws_cloudwatch_log_group.tower.name
}

output "ref_client_runtime_arn" {
  value = var.enable_ref_client ? aws_bedrockagentcore_agent_runtime.ref_client[0].agent_runtime_arn : ""
}
