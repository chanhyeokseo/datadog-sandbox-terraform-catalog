FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

ARG TERRAFORM_VERSION=1.7.0
ARG TARGETARCH
RUN wget https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip && \
    unzip terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip && \
    mv terraform /usr/local/bin/ && \
    rm terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip

WORKDIR /app

COPY webui/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY webui/backend/app/ ./app/

COPY instances/ /app/terraform-source/instances/
COPY modules/ /app/terraform-source/modules/
COPY apps/ /app/terraform-source/apps/

RUN mkdir -p /app/terraform /app/terraform-plugin-cache /tmp/tf-warmup && \
    printf 'terraform {\n  required_providers {\n    aws = {\n      source = "hashicorp/aws"\n    }\n  }\n}\n' > /tmp/tf-warmup/main.tf && \
    TF_PLUGIN_CACHE_DIR=/app/terraform-plugin-cache \
    terraform -chdir=/tmp/tf-warmup init -backend=false -input=false && \
    rm -rf /tmp/tf-warmup

COPY webui/backend/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENV TERRAFORM_DIR=/app/terraform
ENV USE_PARAMETER_STORE=true
ENV TF_PLUGIN_CACHE_DIR=/app/terraform-plugin-cache
ENV TF_PLUGIN_CACHE_MAY_BREAK_DEPENDENCY_LOCK_FILE=1

ENTRYPOINT ["/entrypoint.sh"]
