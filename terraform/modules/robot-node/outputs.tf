output "instance_ids" {
  value = aws_instance.robot[*].id
}

output "public_ips" {
  value = aws_instance.robot[*].public_ip
}

output "private_ips" {
  value = aws_instance.robot[*].private_ip
}
