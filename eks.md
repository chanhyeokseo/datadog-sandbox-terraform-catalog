# How to Use

1. Uncomment the contents of `eks.tf`.
2. Run `terraform apply` command to deploy the configuration:
3. Use the value of the `eks_kubeconfig_command` output to configure access to the EKS cluster. For example:
```
aws eks update-kubeconfig --region ap-northeast-2 --name <cluster-name>
```

If you want to enable AWS Fargate, set the enable_fargate option to true before applying the configuration.

# Deploy Datadog Agent

Choose one of the following methods and follow the README.md instructions:

- **Helm**: `eks/agent-helm/README.md`
- **Datadog Operator**: `eks/agent-datadog-operator/README.md`