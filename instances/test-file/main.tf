terraform {
  required_providers {
    local = {
      source = "hashicorp/local"
    }
  }
}

module "test_file" {
  source = "../../modules/local-file-test"

  filename = "test-file-1.txt"
  content  = "This is test file 1 created by Terraform"
}
