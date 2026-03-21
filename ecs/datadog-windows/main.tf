terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
  }
}

provider "aws" {
  region = var.region
}

variable "region" {
  type = string
}

variable "cluster_name" {
  type = string
}

variable "task_execution_role_arn" {
  type = string
}

variable "datadog_api_key" {
  type      = string
  sensitive = true
}

locals {
  td_raw = jsondecode(file("task-definition.json"))
  td = jsondecode(
    replace(file("task-definition.json"), "__DATADOG_API_KEY__", var.datadog_api_key)
  )
  volume_map = { for v in try(local.td_raw.volumes, []) : v.name => try(v.host.sourcePath, "") }
}

resource "aws_ecs_task_definition" "main" {
  family                   = nonsensitive("${var.cluster_name}-${local.td.family}")
  network_mode             = "bridge"
  requires_compatibilities = ["EC2"]
  execution_role_arn       = var.task_execution_role_arn
  container_definitions    = jsonencode(local.td.containerDefinitions)

  dynamic "volume" {
    for_each = local.volume_map
    content {
      name      = volume.key
      host_path = volume.value != "" ? volume.value : null
    }
  }
}

resource "aws_ecs_service" "main" {
  name                = "${var.cluster_name}-datadog-windows"
  cluster             = var.cluster_name
  task_definition     = aws_ecs_task_definition.main.arn
  scheduling_strategy = "DAEMON"
  launch_type         = "EC2"
}
