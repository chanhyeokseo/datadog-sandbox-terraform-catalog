# # ============================================
# # ECR Repository for FastAPI DogStatsD
# # ============================================

# data "aws_caller_identity" "current" {}
# data "aws_region" "current" {}

# resource "aws_ecr_repository" "fastapi_dogstatsd" {
#   name                 = "fastapi-dogstatsd"
#   image_tag_mutability = "MUTABLE"
#   force_delete         = true

#   image_scanning_configuration {
#     scan_on_push = true
#   }

#   tags = merge(
#     local.project_common_tags,
#     {
#       Name = "fastapi-dogstatsd"
#     }
#   )
# }

# resource "aws_ecr_lifecycle_policy" "fastapi_dogstatsd" {
#   repository = aws_ecr_repository.fastapi_dogstatsd.name

#   policy = jsonencode({
#     rules = [{
#       rulePriority = 1
#       description  = "Keep only last 5 images"
#       selection = {
#         tagStatus     = "any"
#         countType     = "imageCountMoreThan"
#         countNumber   = 5
#       }
#       action = {
#         type = "expire"
#       }
#     }]
#   })
# }

# # Build and push Docker image
# resource "null_resource" "docker_build_push" {
#   triggers = {
#     dockerfile_hash = filemd5("${path.module}/fastapi-dogstatsd/Dockerfile")
#     app_code_hash   = filemd5("${path.module}/fastapi-dogstatsd/dogstatsd.py")
#   }

#   depends_on = [aws_ecr_repository.fastapi_dogstatsd]

#   provisioner "local-exec" {
#     working_dir = "${path.module}/fastapi-dogstatsd"
#     command     = <<-EOT
#       set -e
#       echo "=== Building and Pushing Docker Image ==="
      
#       # Login to ECR
#       echo "Logging in to ECR..."
#       aws ecr get-login-password --region ${data.aws_region.current.name} | \
#         docker login --username AWS --password-stdin ${data.aws_caller_identity.current.account_id}.dkr.ecr.${data.aws_region.current.name}.amazonaws.com
      
#       # Build and push image for linux/amd64 (required for ECS Fargate)
#       echo "Building and pushing Docker image..."
#       docker buildx build \
#         --platform linux/amd64 \
#         --push \
#         -t ${aws_ecr_repository.fastapi_dogstatsd.repository_url}:latest \
#         .
      
#       echo "=== Docker image pushed successfully ==="
#       echo "Image URI: ${aws_ecr_repository.fastapi_dogstatsd.repository_url}:latest"
#     EOT
#   }
# }

# # ECR Module Outputs
# output "ecr_repository_url" {
#   description = "URL of the ECR repository"
#   value       = aws_ecr_repository.fastapi_dogstatsd.repository_url
# }

# output "ecr_repository_arn" {
#   description = "ARN of the ECR repository"
#   value       = aws_ecr_repository.fastapi_dogstatsd.arn
# }

# output "docker_image_uri" {
#   description = "Full Docker image URI"
#   value       = "${aws_ecr_repository.fastapi_dogstatsd.repository_url}:latest"
# }