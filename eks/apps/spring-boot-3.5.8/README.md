# Architecture

- **sandbox-apps namespace**
  - `spring-boot-demo` deployment
    - Spring Boot 3.5.8 with Datadog Java tracer
    - APM test endpoints (custom spans, errors, latency)
  - `spring-boot-demo` service (ClusterIP)
  - `spring-boot-demo-lb` service (LoadBalancer)
  - `spring-boot-load-generator` pod (sends requests to spring-boot-demo)

# Endpoints

| Path | Description |
|------|-------------|
| `/` | Hello World |
| `/add-tag` | Add custom span tags |
| `/set-error` | Set error on span |
| `/trace-annotation` | @Trace annotation span |
| `/manual-span` | Manual span creation |
| `/slow` | 2s latency test |

# Installation

1. Deploy Spring Boot application

```
kubectl apply -f deployment.yaml
```

2. Deploy load generator (Optional)

```
kubectl apply -f load-generator.yaml
```

3. Verify

```
kubectl get pods -n sandbox-apps
kubectl exec <datadog-agent-pod> -c agent -- curl -s http://spring-boot-demo.sandbox-apps.svc.cluster.local/
```

# Uninstallation

```
kubectl delete -f load-generator.yaml
kubectl delete -f deployment.yaml
```
