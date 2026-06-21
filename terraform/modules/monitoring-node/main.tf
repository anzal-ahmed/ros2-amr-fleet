resource "aws_instance" "monitoring" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [var.security_group_id]
  key_name               = var.key_name
  iam_instance_profile   = var.iam_instance_profile

  root_block_device {
    volume_size           = 30
    volume_type           = "gp3"
    delete_on_termination = true
  }

  user_data = <<-EOF
    #!/bin/bash
    hostnamectl set-hostname ros2-monitoring
    echo "ros2-monitoring" > /etc/hostname
  EOF

  tags = {
    Name = "ros2-monitoring-${var.environment}"
    Role = "monitoring"
  }
}
