# Installation

1. Add Helm repo, install operator, and create secret

```
helm repo add datadog https://helm.datadoghq.com
helm install datadog-operator datadog/datadog-operator
kubectl create secret generic datadog-secret --from-literal api-key=<YOUR_DATADOG_API_KEY>
```

2. Update `clusterName` in datadog-agent.yaml with `eks_cluster_name` output value

3. Deploy DatadogAgent

```
kubectl apply -f datadog-agent.yaml
```

# Uninstallation

```
kubectl delete -f datadog-agent.yaml
helm uninstall datadog-operator
kubectl delete secret datadog-secret
```
