terraform {
  backend "s3" {
    bucket         = "anzal-ros2-fleet-tfstate"
    key            = "ros2-amr-fleet/terraform.tfstate"
    region         = "eu-central-1"
    use_lockfile   = true
    encrypt        = true
  }
}
