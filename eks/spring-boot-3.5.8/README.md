# spring-boot-3.5.8

Spring Boot 3.5.8 demo application pre-configured with Datadog Java APM tracer for end-to-end tracing validation on EKS.

## Overview

- **Method**: kubectl manifests
- **Components**:
  - `sandbox-apps` namespace: Spring Boot Deployment, ClusterIP and LoadBalancer Services, load generator
- **APM Integration**: Unified service tags (`DD_SERVICE`, `DD_ENV`, `DD_VERSION`), log injection, profiling, and dynamic instrumentation enabled

## Key Files

- `deployment.yaml` — Namespace, Spring Boot Deployment (with Datadog APM env vars), ClusterIP and LoadBalancer Services
- `load-generator.yaml` — ConfigMap-based load script that exercises all demo endpoints with varied traffic patterns

## Endpoints

| Path | Description |
|------|-------------|
| `/` | Hello World |
| `/add-tag` | Add custom span tags |
| `/set-error` | Set error on span |
| `/trace-annotation` | @Trace annotation span |
| `/manual-span` | Manual span creation |
| `/slow` | 2s latency test |

## Notes

- The `deployment.yaml` references an ECR image URL (`${ECR_REPOSITORY_URL}:spring-boot-3.5.8`) that must be replaced with the actual ECR repository URL.
- The Datadog Agent must be deployed on the cluster for APM data to be collected.
- The load generator is optional and can be deployed separately.
