# ============================================
# EC2 Datadog Host-Based Module
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

# User data script for installing Datadog agent
locals {
  datadog_user_data = <<-EOF
    #!/bin/bash
    set -e
    
    # Update system
    dnf update -y
    
    # Install Datadog Agent
    DD_API_KEY="${var.datadog_api_key}" \
    DD_SITE="${var.datadog_site}" \
    bash -c "$(curl -L https://install.datadoghq.com/scripts/install_script_agent7.sh)"
    
    # Configure the agent with custom tags
    cat >> /etc/datadog-agent/datadog.yaml <<EOL
    tags:
      - env:${var.environment}
      - project:${var.project_name}
      - terraform:true
      - instance_type:${var.instance_type}
    EOL
    
    # Start the agent
    systemctl enable datadog-agent
    systemctl start datadog-agent
    
    echo "Datadog agent installation complete!"
  EOF
}

# EC2 Instance with Host-Based Datadog Agent
resource "aws_instance" "datadog_host" {
  ami           = data.aws_ami.amazon_linux_2023.id
  instance_type = var.instance_type

  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = var.security_group_ids
  associate_public_ip_address = var.associate_public_ip

  key_name = var.key_name

  user_data = local.datadog_user_data

  # Ensure user data runs on change
  user_data_replace_on_change = true

  tags = merge(
    var.common_tags,
    {
      Name = "${var.name_prefix}-host-datadog-agent"
    }
  )
}

