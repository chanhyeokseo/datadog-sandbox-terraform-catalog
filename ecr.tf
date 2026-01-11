# # ============================================
# # ECR Repository for Sandbox Apps
# # ============================================

# module "ecr_apps" {
#   source = "./modules/ecr"

#   repository_name        = "${local.project_name_prefix}-apps"
#   image_tag_mutability   = "MUTABLE"
#   scan_on_push           = true
#   force_delete           = true
#   lifecycle_policy_count = 20  # Keep more images since multiple apps share this repo

#   tags = merge(local.project_common_tags, {
#     Name = "${local.project_name_prefix}-apps"
#   })
# }

# # ECR Repository for Sandbox Apps Outputs
# output "ecr_apps_url" {
#   description = "ECR repository URL for all sandbox apps"
#   value       = module.ecr_apps.repository_url
# }
