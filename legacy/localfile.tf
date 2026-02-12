# ============================================
# Local File Test Module
# ============================================

module "test_file_1" {
  source = "./modules/local-file-test"

  filename = "test-file-1.txt"
  content  = "This is test file 1 created by Terraform"
}

output "test_file_1_file_path" {
  description = "Path of test file 1"
  value       = module.test_file_1.file_path
}

output "test_file_1_file_id" {
  description = "ID of test file 1"
  value       = module.test_file_1.file_id
}

module "test_file_2" {
  source = "./modules/local-file-test"

  filename = "test-file-2.txt"
  content  = "This is test file 2 for quick testing"
}

output "test_file_2_file_path" {
  description = "Path of test file 2"
  value       = module.test_file_2.file_path
}

output "test_file_2_file_id" {
  description = "ID of test file 2"
  value       = module.test_file_2.file_id
}

module "test_file_3" {
  source = "./modules/local-file-test"

  filename = "test-file-3.txt"
  content  = "This is test file 3 - fast deploy/destroy cycle"
}

output "test_file_3_file_path" {
  description = "Path of test file 3"
  value       = module.test_file_3.file_path
}

output "test_file_3_file_id" {
  description = "ID of test file 3"
  value       = module.test_file_3.file_id
}
