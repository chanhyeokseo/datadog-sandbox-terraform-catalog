terraform {
  required_providers {
    local = {
      source = "hashicorp/local"
    }
  }
}

module "test_file" {
  source = "../../modules/local-file-test"

  filename = "test-file-3.txt"
  content  = "This is test file 3 - fast deploy/destroy cycle"
}
