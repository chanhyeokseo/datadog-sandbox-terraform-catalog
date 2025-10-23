# ============================================
# EC2 Datadog Docker Module
# ============================================

# Data source for Amazon Linux 2023 AMI
data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# User data script for running Datadog agent container
locals {
  docker_datadog_user_data = <<-EOF
    #!/bin/bash
    set -e
    
    echo "=== Starting Datadog Docker Agent Setup ==="

    # Run Datadog Agent container
    echo "Starting Datadog Agent container..."
    docker run -d \
      --name dd-agent \
      -e DD_API_KEY="${var.datadog_api_key}" \
      -e DD_SITE="${var.datadog_site}" \
      -e DD_DOGSTATSD_NON_LOCAL_TRAFFIC=true \
      -e DD_TAGS="env:${var.environment},project:${var.project_name},terraform:true,instance_type:${var.instance_type}" \
      -v /var/run/docker.sock:/var/run/docker.sock:ro \
      -v /proc/:/host/proc/:ro \
      -v /sys/fs/cgroup/:/host/sys/fs/cgroup:ro \
      -v /var/lib/docker/containers:/var/lib/docker/containers:ro \
      gcr.io/datadoghq/agent:7
    
    echo "=== Datadog Docker Agent Setup Complete ==="
  EOF
}

# EC2 Instance with Docker Datadog Agent
resource "aws_instance" "datadog_host" {
  ami           = data.aws_ami.amazon_linux_2023.id
  instance_type = var.instance_type

  subnet_id              = var.subnet_id
  vpc_security_group_ids = var.security_group_ids
  associate_public_ip_address = var.associate_public_ip

  key_name = var.key_name

  user_data = local.docker_datadog_user_data

  # Ensure user data runs on change
  user_data_replace_on_change = true

  tags = merge(
    var.common_tags,
    {
      Name = "${var.name_prefix}-docker-datadog-host"
    }
  )
}

