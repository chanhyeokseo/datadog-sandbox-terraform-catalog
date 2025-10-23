# ============================================
# EC2 Instance with Dockerized Datadog Agent
# ============================================

# User data script for running Datadog agent container
# Note: Docker is pre-installed in Amazon Linux 2023
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
      -v /var/run/docker.sock:/var/run/docker.sock:ro \
      -v /proc/:/host/proc/:ro \
      -v /sys/fs/cgroup/:/host/sys/fs/cgroup:ro \
      -v /var/lib/docker/containers:/var/lib/docker/containers:ro \
      gcr.io/datadoghq/agent:7
    
    echo "=== Datadog Docker Agent Setup Complete ==="
  EOF
}

# EC2 Instance with Docker Datadog Agent
resource "aws_instance" "docker_datadog_host" {
  ami           = data.aws_ami.amazon_linux_2023.id
  instance_type = var.ec2_instance_type

  subnet_id = aws_subnet.public.id
  # Attach both shared and personal security groups
  vpc_security_group_ids = [
    aws_security_group.personal_ec2.id
  ]
  associate_public_ip_address = true

  key_name = var.ec2_key_name

  user_data = local.docker_datadog_user_data

  # Ensure user data runs on change
  user_data_replace_on_change = true

  tags = merge(
    local.project_common_tags,
    {
      Name = "${local.project_name_prefix}-docker-datadog-host"
    }
  )
}

# ============================================
# Outputs
# ============================================

output "docker_datadog_ssh_command" {
  description = "SSH command to connect to the Docker Datadog EC2 host"
  value       = "ssh -i ${var.ec2_key_name}.pem ec2-user@${aws_instance.docker_datadog_host.public_ip}"
}

