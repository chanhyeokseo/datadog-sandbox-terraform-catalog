terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.38.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "3.2.4"
    }
  }
}
provider "aws" {
  region = var.region
}

module "deploy_spring_boot" {
  source = "../../modules/app-deploy"

  app_name           = "spring-boot-demo"
  app_path           = "${path.module}/../../apps/spring-boot-3.5.8"
  ecr_repository_url = var.ecr_repository_url
  aws_region         = var.region
  image_tag          = "spring-boot-3.5.8"
  build_args = {
    DD_AGENT_VERSION = "1.25.1"
  }
}
