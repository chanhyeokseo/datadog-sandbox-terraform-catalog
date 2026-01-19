# ============================================
# EC2 Forwardog Module
# ============================================

locals {
  forwardog_user_data = <<-EOF
    #!/bin/bash
    set -e
    
    echo "=== Starting Forwardog Setup ==="

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

    # Create working directory
    mkdir -p /opt/forwardog
    cd /opt/forwardog

    # Create docker-compose.yml
    cat > /opt/forwardog/docker-compose.yml << 'COMPOSE'
    version: "3.8"

    services:
      forwardog:
        image: ${var.forwardog_image}
        container_name: forwardog
        ports:
          - "8000:8000"
        environment:
          - DD_API_KEY=${var.datadog_api_key}
          - DD_SITE=${var.datadog_site}
          - DD_AGENT_HOST=datadog-agent
          - DOGSTATSD_PORT=8125
        volumes:
          - forwardog-logs:/var/log/forwardog
        networks:
          - forwardog-network
        depends_on:
          - datadog-agent
        restart: unless-stopped

      datadog-agent:
        image: ${var.datadog_agent_image}
        container_name: datadog-agent
        environment:
          - DD_API_KEY=${var.datadog_api_key}
          - DD_SITE=${var.datadog_site}
          - DD_DOGSTATSD_NON_LOCAL_TRAFFIC=true
          - DD_LOGS_ENABLED=true
          - DD_LOGS_CONFIG_CONTAINER_COLLECT_ALL=false
          - DD_LOGS_CONFIG_AUTO_MULTI_LINE_DETECTION=true
          - DD_LOGS_CONFIG_FORCE_USE_HTTP=true
          - DD_HOSTNAME=forwardog-agent
          - DD_TAGS=env:${var.environment},project:${var.project_name},service:forwardog,terraform:true
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock:ro
          - /proc/:/host/proc/:ro
          - /sys/fs/cgroup/:/host/sys/fs/cgroup:ro
          - forwardog-logs:/var/log/forwardog:ro
        ports:
          - "8125:8125/udp"
        networks:
          - forwardog-network
        restart: unless-stopped

    volumes:
      forwardog-logs:
        driver: local

    networks:
      forwardog-network:
        driver: bridge
    COMPOSE

    # Install Docker Compose plugin
    echo "Installing Docker Compose..."
    mkdir -p /usr/local/lib/docker/cli-plugins
    curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

    # Wait for Docker to be fully ready
    sleep 5

    # Start Forwardog stack
    echo "Starting Forwardog stack..."
    cd /opt/forwardog
    docker compose up -d

    echo "=== Forwardog Setup Complete ==="
  EOF
}

resource "aws_instance" "forwardog" {
  ami           = var.custom_ami_id
  instance_type = var.instance_type

  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = var.security_group_ids
  associate_public_ip_address = var.associate_public_ip

  key_name = var.key_name

  user_data = local.forwardog_user_data

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
        Name    = "${var.name_prefix}-forwardog-root"
        service = var.service
      }
    )
  }

  tags = merge(
    var.common_tags,
    {
      Name    = "${var.name_prefix}-forwardog"
      service = var.service
    }
  )
}

