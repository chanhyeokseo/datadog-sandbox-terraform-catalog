FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    git \
    && rm -rf /var/lib/apt/lists/*

ARG TARGETARCH

ARG TERRAFORM_VERSION=1.7.0
RUN wget https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip && \
    unzip terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip && \
    mv terraform /usr/local/bin/ && \
    rm terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip

ARG KUBECTL_VERSION=1.31.0
RUN wget -q https://dl.k8s.io/release/v${KUBECTL_VERSION}/bin/linux/${TARGETARCH}/kubectl \
    -O /usr/local/bin/kubectl && chmod +x /usr/local/bin/kubectl

ARG HELM_VERSION=3.16.0
RUN wget -q https://get.helm.sh/helm-v${HELM_VERSION}-linux-${TARGETARCH}.tar.gz \
    -O /tmp/helm.tar.gz && tar -xzf /tmp/helm.tar.gz -C /tmp \
    && mv /tmp/linux-${TARGETARCH}/helm /usr/local/bin/helm \
    && rm -rf /tmp/helm.tar.gz /tmp/linux-${TARGETARCH}

WORKDIR /app

COPY webui/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY webui/backend/app/ ./app/

COPY instances/ /app/terraform-source/instances/
COPY modules/ /app/terraform-source/modules/
COPY apps/ /app/terraform-source/apps/
COPY eks/ /app/terraform-source/eks/

RUN mkdir -p /app/terraform

COPY webui/backend/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENV TERRAFORM_DIR=/app/terraform
ENV USE_PARAMETER_STORE=true
ENV TF_PLUGIN_CACHE_DIR=/app/terraform/.plugin-cache
ENV TF_PLUGIN_CACHE_MAY_BREAK_DEPENDENCY_LOCK_FILE=1

ENTRYPOINT ["/entrypoint.sh"]
