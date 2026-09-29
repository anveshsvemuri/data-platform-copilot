output "ecr_repository_url" {
  description = "Repository to receive the immutable copilot image."
  value       = aws_ecr_repository.copilot.repository_url
}

output "mcp_endpoint" {
  description = "Authenticated Streamable HTTP MCP endpoint."
  value       = local.server_url
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.copilot.name
}
