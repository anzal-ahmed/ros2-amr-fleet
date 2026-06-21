output "github_actions_role_arn" {
  description = "IAM role ARN for GitHub Actions OIDC — set as GH_ACTIONS_ROLE_ARN repo variable"
  value       = aws_iam_role.github_actions.arn
}

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "robot_instance_ids" {
  description = "EC2 instance IDs for robot nodes"
  value       = module.robot_nodes.instance_ids
}

output "robot_public_ips" {
  description = "Public IPs of robot nodes"
  value       = module.robot_nodes.public_ips
}

output "robot_private_ips" {
  description = "Private IPs of robot nodes (used for DDS peer config)"
  value       = module.robot_nodes.private_ips
}

output "monitoring_instance_id" {
  description = "EC2 instance ID for monitoring node"
  value       = module.monitoring_node.instance_id
}

output "monitoring_public_ip" {
  description = "Public IP of monitoring node"
  value       = module.monitoring_node.public_ip
}

output "grafana_url" {
  description = "Grafana dashboard URL (after Ansible install)"
  value       = "http://${module.monitoring_node.public_ip}:3000"
}

output "prometheus_url" {
  description = "Prometheus URL (after Ansible install)"
  value       = "http://${module.monitoring_node.public_ip}:9090"
}

output "ssh_robot_cmd" {
  description = "SSH command template for robot nodes"
  value       = "ssh -i ~/.ssh/ros2_fleet_key ubuntu@<robot_public_ip>"
}

output "ssh_monitoring_cmd" {
  description = "SSH command for monitoring node"
  value       = "ssh -i ~/.ssh/ros2_fleet_key ubuntu@${module.monitoring_node.public_ip}"
}
