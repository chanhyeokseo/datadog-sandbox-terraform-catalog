# agent-helm

Datadog Agent deployment using the official Datadog Helm chart.
This is the standard and most common approach for installing the Datadog Agent on EKS clusters.

## Overview

- **Method**: Helm chart (`datadog/datadog`)
- **Configuration**: All agent settings are managed through `datadog-values.yaml`
- **Components**: Deploys DaemonSet (node agent), Cluster Agent, and optional integrations based on values

## Key Files

- `datadog-values.yaml` — Helm values for agent configuration (API key, site, log/APM/process collection toggles, cluster name, etc.)

## Notes

- The `clusterName` field in `datadog-values.yaml` should match the EKS cluster name from Terraform outputs.
- A Kubernetes secret `datadog-secret` is created to store the Datadog API key securely.
- Use the **Update** action after modifying `datadog-values.yaml` to apply changes to a running deployment.
- For advanced configuration options, see the [Datadog Helm chart documentation](https://github.com/DataDog/helm-charts/tree/main/charts/datadog).
