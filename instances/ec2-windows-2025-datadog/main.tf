# EC2 Windows Server 2025 with Datadog Host Agent
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.38.0"
    }
  }
}
provider "aws" {
  region = var.region
}

data "aws_ami" "windows_2025" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["Windows_Server-2025-English-Full-Base-*"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }
}
data "aws_subnet" "public" {
  id = var.public_subnet_id
}
data "aws_security_group" "personal_sg" {
  name   = "${var.name_prefix}-personal-sg"
  vpc_id = var.vpc_id
}

locals {
  name_prefix = var.name_prefix
  common_tags = {
    ManagedBy = "Terraform"
    creator   = var.creator
    team      = var.team
  }
  vpc = {
    public_subnet_id = data.aws_subnet.public.id
  }
  security_group_ids = length(var.security_group_ids) > 0 ? var.security_group_ids : [data.aws_security_group.personal_sg.id]
}

module "ec2_windows_2025_datadog" {
  source = "../../modules/ec2-basic"

  name_prefix        = "${local.name_prefix}-windows-2025-dd"
  instance_type      = var.ec2_instance_type
  subnet_id          = local.vpc.public_subnet_id
  security_group_ids = local.security_group_ids
  key_name            = var.ec2_key_name
  custom_ami_id       = data.aws_ami.windows_2025.id
  associate_public_ip        = var.ec2_associate_public_ip
  root_volume_size           = var.ec2_root_volume_size
  root_volume_type           = var.ec2_root_volume_type
  enable_detailed_monitoring = var.ec2_enable_detailed_monitoring
  get_password_data   = true
  common_tags         = local.common_tags

  user_data                   = local.windows_datadog_userdata
  user_data_replace_on_change = true
}

locals {
  windows_datadog_userdata = <<-USERDATA
    <powershell>
    Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
    Set-Service -Name sshd -StartupType Automatic
    Start-Service sshd
    Set-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -Profile Any
    New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShell -Value "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -PropertyType String -Force

    $token = Invoke-RestMethod -Uri "http://169.254.169.254/latest/api/token" -Method PUT -Headers @{"X-aws-ec2-metadata-token-ttl-seconds"="21600"}
    $key = Invoke-RestMethod -Uri "http://169.254.169.254/latest/meta-data/public-keys/0/openssh-key" -Headers @{"X-aws-ec2-metadata-token"=$token}
    $keyPath = "C:\ProgramData\ssh\administrators_authorized_keys"
    Set-Content -Path $keyPath -Value $key -Encoding UTF8
    icacls $keyPath /inheritance:r /grant "SYSTEM:(R)" /grant "Administrators:(R)"

    Restart-Service sshd

    $p = Start-Process -Wait -PassThru msiexec -ArgumentList '/qn /i "https://windows-agent.datadoghq.com/datadog-agent-7-latest.amd64.msi" /log C:\Windows\SystemTemp\install-datadog.log APIKEY="${data.aws_ssm_parameter.datadog_api_key.value}" SITE="${var.datadog_site}"'
    if ($p.ExitCode -ne 0) {
      Write-Host "msiexec failed with exit code $($p.ExitCode) please check the logs at C:\Windows\SystemTemp\install-datadog.log" -ForegroundColor Red
    }
    </powershell>
  USERDATA
}
