# Architecture

- **istio-system namespace**
  - `istio-base`: Istio CRDs and cluster-wide resources
  - `istiod`: Istio control plane

- **flask-app namespace** (istio-injection enabled)
  - `flask-server` pod
    - Flask container (application)
    - Envoy sidecar (auto-injected, handles traffic)
  - `flask-server` service
  - `load-generator` pod (sends requests to flask-server)

# Installation

1. Install Istio using Helm

```
helm repo add istio https://istio-release.storage.googleapis.com/charts
helm repo update

kubectl create namespace istio-system
helm install istio-base istio/base -n istio-system --set defaultRevision=default
helm install istiod istio/istiod -n istio-system --wait
```

2. Deploy Flask server with Istio sidecar

```
kubectl apply -f flask-server.yaml
```

> Note: `flask-server.yaml` creates a dedicated `flask-app` namespace with `istio-injection: enabled` label. Sidecar injection only applies to pods in this namespace.

3. Deploy load generator (Optional)

```
kubectl apply -f load-generator.yaml
```

# Uninstallation

```
kubectl delete -f load-generator.yaml
kubectl delete -f flask-server.yaml
helm uninstall istiod -n istio-system
helm uninstall istio-base -n istio-system
kubectl delete namespace istio-system
```
