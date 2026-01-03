# ============================================
# EC2 Datadog Docker Module
# ============================================

locals {
  docker_datadog_user_data = <<-EOF
    #!/bin/bash
    set -e
    
    echo "=== Starting Datadog Docker Agent Setup ==="

    # Install Docker
    echo "Installing Docker..."
    yum update -y
    yum install -y docker
    
    # Start Docker service
    echo "Starting Docker service..."
    systemctl start docker
    systemctl enable docker
    
    # Add ec2-user to docker group
    usermod -a -G docker ec2-user

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
      gcr.io/datadoghq/agent:7.72.1
    
    echo "=== Datadog Docker Agent Setup Complete ==="
  EOF
}

resource "aws_instance" "datadog_host" {
  ami           = var.custom_ami_id
  instance_type = var.instance_type

  subnet_id              = var.subnet_id
  vpc_security_group_ids = var.security_group_ids
  associate_public_ip_address = var.associate_public_ip

  key_name = var.key_name

  user_data = local.docker_datadog_user_data

  user_data_replace_on_change = true

  lifecycle {
    ignore_changes = [ami]
  }

  root_block_device {
    volume_size           = 30
    volume_type           = "gp3"
    delete_on_termination = true
    encrypted             = true

    tags = merge(
      var.common_tags,
      {
        Name    = "${var.name_prefix}-docker-datadog-host-root"
        service = var.service
      }
    )
  }

  tags = merge(
    var.common_tags,
    {
      Name    = "${var.name_prefix}-docker-datadog-host"
      service = var.service
    }
  )
}