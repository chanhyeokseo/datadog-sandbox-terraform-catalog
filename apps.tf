# # ============================================
# # Deploy APM Sandbox Apps to ECR
# # ============================================

# # ============================================
# # Spring Boot Demo App - Build & Push
# # ============================================
# module "deploy_spring_boot" {
#   source = "./modules/app-deploy"

#   app_name           = "spring-boot-demo"
#   app_path           = "${path.module}/apps/spring-boot-3.5.8"
#   ecr_repository_url = module.ecr_apps.repository_url
#   aws_region         = var.region
#   image_tag          = "spring-boot-3.5.8"  # Use app name as tag

#   build_args = {
#     DD_AGENT_VERSION = "1.25.1"
#   }

#   depends_on = [module.ecr_apps]
# }

# # Spring Boot Demo App - Build & Push Outputs
# output "spring_boot_image_uri" {
#   description = "Full image URI for Spring Boot app"
#   value       = module.deploy_spring_boot.image_uri
# }
