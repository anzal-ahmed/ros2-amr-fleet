resource "aws_instance" "robot" {
  count                  = var.robot_count
  ami                    = var.ami_id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_ids[count.index % length(var.subnet_ids)]
  vpc_security_group_ids = [var.security_group_id]
  key_name               = var.key_name
  iam_instance_profile   = var.iam_instance_profile

  root_block_device {
    volume_size           = 20
    volume_type           = "gp3"
    delete_on_termination = true
  }

  user_data = <<-EOF
    #!/bin/bash
    hostnamectl set-hostname ros2-robot-${count.index + 1}
    echo "ros2-robot-${count.index + 1}" > /etc/hostname
  EOF

  tags = {
    Name     = "ros2-robot-${count.index + 1}-${var.environment}"
    Role     = "robot-node"
    RobotID  = "robot-${count.index + 1}"
  }
}
