# Installation

1. Add Helm repo and create secret

```
helm repo add datadog https://helm.datadoghq.com
helm repo update
kubectl create secret generic datadog-secret --from-literal api-key=<YOUR_DATADOG_API_KEY>
```

2. Update `clusterName` in datadog-values.yaml with `eks_cluster_name` output value

3. Install Datadog Agent

```
helm install datadog-agent -f datadog-values.yaml datadog/datadog
```

# Uninstallation

```
helm uninstall datadog-agent
kubectl delete secret datadog-secret
```
