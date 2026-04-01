# Datadog Agent - Operator (Fargate)

Deploys the Datadog Agent for EKS Fargate using the Datadog Operator with Admission Controller sidecar injection.

## Prerequisites

### Fargate Profile

A Fargate Profile must be configured in your EKS cluster to match the `fargate` namespace.
Pods deployed to this namespace will be scheduled on Fargate nodes instead of EC2.

Example Fargate Profile selector:

```
Namespace: fargate
```

### Namespace & Secret

This preset automatically:

1. Creates `datadog-secret` in the default namespace (for Cluster Agent)
2. Creates the `fargate` namespace
3. Copies `datadog-secret` into the `fargate` namespace (for sidecar agents injected into app pods)

If you use additional namespaces with Fargate Profiles, copy the secret manually:

```bash
kubectl create secret generic datadog-secret -n <your-namespace> \
  --from-literal api-key=$(kubectl get secret datadog-secret -o jsonpath='{.data.api-key}' | base64 -d) \
  --from-literal token=$(kubectl get secret datadog-secret -o jsonpath='{.data.token}' | base64 -d)
```

## How It Works

- `nodeAgent` (DaemonSet) is disabled — Fargate does not support DaemonSets
- `clusterAgent` runs on an EC2 node and manages the Admission Controller
- The Admission Controller automatically injects a Datadog Agent sidecar into pods labeled with `agent.datadoghq.com/sidecar: fargate`
- App presets with `-fargate` suffix include this label and deploy to the `fargate` namespace
