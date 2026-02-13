terraform {
  required_providers {
    local = {
      source = "hashicorp/local"
    }
  }
}

module "test_file" {
  source = "git::https://github.com/chanhyeokseo/datadog-sandbox-terraform-catalog.git//modules/local-file-test?ref=webui-dev"

  filename = "test-file-2.txt"
  content  = "This is test file 2 for quick testing"
}
