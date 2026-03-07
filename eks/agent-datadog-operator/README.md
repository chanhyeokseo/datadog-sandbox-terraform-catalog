# agent-datadog-operator

Datadog Agent deployment using the Datadog Operator with a `DatadogAgent` custom resource.
This approach provides a Kubernetes-native, declarative way to manage the Datadog Agent lifecycle.

## Overview

- **Method**: Datadog Operator + `DatadogAgent` CRD
- **Configuration**: Agent behavior is defined in `datadog-agent.yaml` as a Kubernetes custom resource
- **Components**: The Operator watches for `DatadogAgent` resources and manages DaemonSet, Cluster Agent, and Cluster Checks Runner automatically

## Key Files

- `datadog-agent.yaml` — `DatadogAgent` custom resource definition specifying agent features (APM, logs, process monitoring, etc.)

## Notes

- The Datadog Operator is installed via Helm (`datadog/datadog-operator`) and manages the agent lifecycle.
- A Kubernetes secret `datadog-secret` is created to store the Datadog API key securely.
- The Operator approach is recommended when you want GitOps-friendly, CRD-based management of the agent.
- Use the **Update** action after modifying `datadog-agent.yaml` to reconcile changes.
- For advanced configuration options, see the [Datadog Operator documentation](https://docs.datadoghq.com/containers/datadog_operator/).
