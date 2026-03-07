# istio

Istio service mesh deployment with a Flask demo application for testing sidecar proxy injection and traffic management.

## Overview

- **Method**: Helm charts (`istio/base`, `istio/istiod`) + kubectl manifests
- **Components**:
  - `istio-system` namespace: Istio CRDs (`istio-base`) and control plane (`istiod`)
  - `flask-app` namespace: Flask server with auto-injected Envoy sidecar, load generator
- **Sidecar Injection**: Enabled via `istio-injection: enabled` label on the `flask-app` namespace

## Key Files

- `flask-server.yaml` — Namespace, Flask Deployment, and Service with Istio sidecar injection
- `load-generator.yaml` — Load generator that sends weighted HTTP requests (2xx/4xx/5xx mix)

## Notes

- The Flask server exposes multiple endpoints (`/`, `/api/success`, `/api/error`, etc.) to generate diverse HTTP status codes for Istio observability.
- The load generator is optional and can be deployed separately.
- For Datadog integration with Istio, ensure the Datadog Agent is deployed with Istio metrics collection enabled.
