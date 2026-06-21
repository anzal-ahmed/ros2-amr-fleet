data "aws_ami" "ubuntu_22_04" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_key_pair" "ros2_fleet" {
  key_name   = "ros2-fleet-key-${var.environment}"
  public_key = file(var.ssh_public_key_path)
}

# OIDC provider so GitHub Actions can authenticate to AWS without long-lived keys
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

resource "aws_iam_role" "github_actions" {
  name = "ros2-fleet-github-actions-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.github.arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringLike = {
          "token.actions.githubusercontent.com:sub" = "repo:anzal-ahmed/ros2-amr-fleet:*"
        }
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "github_actions_terraform" {
  name = "ros2-fleet-terraform-policy"
  role = aws_iam_role.github_actions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:*", "vpc:*",
          "iam:*",
          "s3:*",
          "dynamodb:*",
          "ssm:*"
        ]
        Resource = "*"
      }
    ]
  })
}

# IAM role for SSM (Fleet Manager) — attached to all EC2 instances
resource "aws_iam_role" "ec2_ssm" {
  name = "ros2-fleet-ec2-ssm-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.ec2_ssm.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ec2_ssm" {
  name = "ros2-fleet-ec2-ssm-profile"
  role = aws_iam_role.ec2_ssm.name
}

# VPC
module "vpc" {
  source              = "./modules/vpc"
  vpc_cidr            = var.vpc_cidr
  public_subnet_cidrs = var.public_subnet_cidrs
  availability_zones  = var.availability_zones
  environment         = var.environment
}

# Security group for robot nodes
resource "aws_security_group" "robot" {
  name        = "ros2-robot-sg-${var.environment}"
  description = "Robot AMR nodes - SSH, DDS, node-exporter"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }

  # CycloneDDS discovery + data (UDP)
  ingress {
    description = "DDS intra-fleet"
    from_port   = 7400
    to_port     = 7500
    protocol    = "udp"
    cidr_blocks = [var.vpc_cidr]
  }

  # Prometheus node_exporter scrape from monitoring node
  ingress {
    description     = "node-exporter"
    from_port       = 9100
    to_port         = 9100
    protocol        = "tcp"
    security_groups = [aws_security_group.monitoring.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Security group for monitoring node
resource "aws_security_group" "monitoring" {
  name        = "ros2-monitoring-sg-${var.environment}"
  description = "Monitoring node - Prometheus + Grafana"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }

  ingress {
    description = "Grafana UI"
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Prometheus UI"
    from_port   = 9090
    to_port     = 9090
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Robot nodes
module "robot_nodes" {
  source               = "./modules/robot-node"
  robot_count          = var.robot_count
  instance_type        = var.robot_instance_type
  ami_id               = data.aws_ami.ubuntu_22_04.id
  subnet_ids           = module.vpc.public_subnet_ids
  security_group_id    = aws_security_group.robot.id
  key_name             = aws_key_pair.ros2_fleet.key_name
  iam_instance_profile = aws_iam_instance_profile.ec2_ssm.name
  environment          = var.environment
}

# Monitoring node
module "monitoring_node" {
  source               = "./modules/monitoring-node"
  instance_type        = var.monitoring_instance_type
  ami_id               = data.aws_ami.ubuntu_22_04.id
  subnet_id            = module.vpc.public_subnet_ids[0]
  security_group_id    = aws_security_group.monitoring.id
  key_name             = aws_key_pair.ros2_fleet.key_name
  iam_instance_profile = aws_iam_instance_profile.ec2_ssm.name
  environment          = var.environment
}
