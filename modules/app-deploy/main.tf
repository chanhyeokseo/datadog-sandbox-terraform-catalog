
locals {
  build_args_string = join(" ", [
    for k, v in var.build_args : "--build-arg ${k}=${v}"
  ])

  full_image_uri = "${var.ecr_repository_url}:${var.image_tag}"
}

data "external" "source_hash" {
  program = ["bash", "-c", <<-EOF
    cd "${var.app_path}"
    # Hash key files: Dockerfile, pom.xml/build.gradle, and Java source files
    HASH=$(find . -type f \( -name "Dockerfile" -o -name "pom.xml" -o -name "build.gradle" -o -name "*.java" -o -name "*.properties" -o -name "*.yaml" -o -name "*.yml" \) -exec sha256sum {} \; 2>/dev/null | sort | sha256sum | cut -d' ' -f1)
    echo "{\"hash\": \"$HASH\"}"
  EOF
  ]
}

resource "null_resource" "docker_build_push" {
  triggers = {
    source_hash   = data.external.source_hash.result["hash"]
    image_uri     = local.full_image_uri
    dockerfile    = var.dockerfile_path
    force_rebuild = var.force_rebuild
  }

  provisioner "local-exec" {
    command = <<-EOF
      set -e
      
      echo "=== Building Docker image for ${var.app_name} ==="
      
      aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin ${var.ecr_repository_url}
      
      cd "${var.app_path}"
      docker build --platform linux/amd64 ${local.build_args_string} -f ${var.dockerfile_path} -t ${local.full_image_uri} .
      
      echo "=== Pushing image to ECR ==="
      docker push ${local.full_image_uri}
      
      echo "=== Done: ${local.full_image_uri} ==="
    EOF
  }
}


