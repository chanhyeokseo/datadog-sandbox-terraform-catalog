terraform {
  required_providers {
    local = {
      source = "hashicorp/local"
    }
  }
}

module "test_file" {
  source = "git::https://github.com/chanhyeokseo/datadog-sandbox-terraform-catalog.git//modules/local-file-test?ref=webui-dev"

  filename = "test-file-1.txt"
  content  = "This is test file 1 created by Terraform"
}
