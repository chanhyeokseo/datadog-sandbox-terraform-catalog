# Resource Naming and Conventions

This document defines naming and structural conventions for Terraform resources, variables, and outputs so that the Web UI and automation can read them consistently.

## Root Configuration (terraform.tfvars)

Values are set in `terraform.tfvars` and passed to the root module and `instances/shared`. Key identifiers:

| Variable | Purpose | Example |
|----------|---------|---------|
| `creator` | Resource creator (firstname.lastname) | `"firstname.lastname"` |
| `team` | Team name | `"technical-support-engineering"` |
| `ec2_key_name` | EC2 key pair name for SSH | Set by onboarding; format `creator-team` |
| `region` | AWS region | `"ap-northeast-2"` |
| `vpc_id`, `public_subnet_id`, `public_subnet2_id`, `private_subnet_id` | Network IDs from onboarding | |

## Naming Rules

### Name prefix

Used for resource names and tags across instances:

- **Formula:** `{creator}-{team}`
- **Example:** `firstname.lastname-technical-support-engineering`
- **Defined in:** `instances/shared` locals → `name_prefix`, `common_tags`

### EC2 key pair name

- **Formula:** `{creator}-{team}` (sanitized for AWS: alphanumeric, `-`, `_` only; max 64 chars)
- **Example:** `firstname.lastname-technical-support-engineering`
- **Set by:** Web UI onboarding (Create Key Pair); stored in `terraform.tfvars` as `ec2_key_name`
- **Key file:** `keys/{ec2_key_name}.pem` under the project root

## Instance Output Conventions

The Web UI reads `terraform output -json` per instance and expects **standard output names** for SSH/Connect to work.

### EC2 / SSH-capable instances

Use these output names so the UI can find SSH command, instance ID, and public IP:

| Output name | Description | Required for Connect |
|-------------|-------------|----------------------|
| `ssh_command` | Full SSH command string (e.g. `ssh -i keys/xxx.pem ec2-user@<ip>`) | Yes |
| `instance_id` | EC2 instance ID | Optional (for display) |
| `public_ip` | Instance public IP | Fallback if hostname cannot be parsed from `ssh_command` |

**Example (instances/ec2-basic/outputs.tf):**

```hcl
output "instance_id" {
  description = "ID of the EC2 instance"
  value       = module.ec2_basic.instance_id
}

output "public_ip" {
  description = "Public IP of the EC2 instance"
  value       = module.ec2_basic.instance_public_ip
}

output "ssh_command" {
  description = "SSH command to connect to the EC2 instance"
  value       = module.ec2_basic.ssh_command
}
```

**Legacy / alternate names:** The UI also accepts `ec2_ssh` (as `ssh_command`), `ec2_ip` (as `public_ip`), and `ec2_id` (as `instance_id`) for backward compatibility. Prefer the standard names for new or updated instances.

### RDS / database instances

| Output name | Description |
|-------------|-------------|
| `rds_endpoint` | RDS endpoint hostname |
| `rds_port` | RDS port |

### Standard output names by resource type

All instances under `instances/` use these **standard output names** (no module-prefixed names like `ec2_basic_instance_id`):

| Type | Output names |
|------|----------------|
| EC2 / SSH | `instance_id`, `public_ip`, `ssh_command` |
| EC2 Windows | `instance_id`, `public_ip`, `rdp_info` |
| DBM | `instance_id`, `public_ip`, `ssh_command`, `rds_endpoint`, `rds_port` |
| ECS | `cluster_name`, `cluster_arn` (ec2 also: `autoscaling_group_name`) |
| EKS | `cluster_name`, `cluster_endpoint`, `kubeconfig_command`, `windows_node_group_name` |
| Lambda | `function_name`, `function_url` |
| ECR | `repository_url` |
| Deploy (e.g. spring-boot) | `image_uri` |

Instance-specific outputs use short names (e.g. `forwardog_url` for ec2-forwardog). Only SSH-related outputs are required for the Web UI Connect button; other names keep the UI and scripts consistent.

## DBM resources (EC2 + RDS bundle)

Each DBM instance is one resource that creates both EC2 and RDS:

| Instance directory   | Web UI resource ID/name   | Contents                    |
|----------------------|---------------------------|-----------------------------|
| `instances/dbm-autoconfig-postgres` | `dbm_autoconfig_postgres` | EC2 (Datadog host) + RDS (Postgres) |
| `instances/dbm-postgres-postgres`   | `dbm_postgres_postgres`   | EC2 (Datadog host) + RDS (Postgres) |

The UI shows one entry per instance (e.g. `dbm_autoconfig_postgres`), not per module. Plan/Apply/Destroy run for the whole instance and thus manage both EC2 and RDS together.

## Instance Variables

Each instance under `instances/<name>/` can declare its own `variables.tf`. Common variables passed from root or shared:

- From **shared:** `name_prefix`, `common_tags`, `security_group_id`, `public_subnet_id`, `public_subnet2_id`, `private_subnet_id`, `vpc_id`, `ec2_key_name`
- From **root:** `region`, `ec2_instance_type`, `creator`, `team`, and service-specific variables (e.g. `datadog_api_key`, `rds_password`)

Use the same variable names as in `variables.tf` (root) and `instances/shared/variables.tf` so that `terraform.tfvars` and the Web UI variable list stay consistent.

## Module Conventions (modules/)

All modules under `modules/` follow these rules:

| Module type | Primary resource name | Example |
|-------------|-----------------------|---------|
| EC2 (ec2-basic, ec2-datadog-docker, ec2-datadog-host, ec2-forwardog) | `aws_instance.instance` | One EC2 instance per module |
| security-group | `aws_security_group.main` | One security group |
| RDS | `aws_db_instance.main`, `aws_security_group.db` | RDS uses `.main` for DB/subnet groups, `.db` for SG |
| ECR | `aws_ecr_repository.this` | Single repository |
| ECS | `aws_ecs_cluster.main` | Cluster and related resources use `.main` |
| EKS | `aws_eks_cluster.main` | Cluster and related resources use `.main` |
| Lambda | `aws_lambda_function.function` | Function and URL |
| app-deploy | `null_resource.docker_build_push` | No long-lived cloud resource |

- **Tags:** `merge(var.common_tags, { Name = "...", service = var.service })` with `var.service` default per module (e.g. `ec2`, `rds`, `ecs`, `eks`).
- **Variables:** Required inputs first (`name_prefix`, `instance_type`, etc.), then optional with defaults. Same variable names across EC2 modules (`name_prefix`, `instance_type`, `custom_ami_id`, `subnet_id`, `security_group_ids`, `key_name`, `common_tags`, `service`).
- **Outputs:** EC2 modules expose `instance_id`, `instance_public_ip`, `ssh_command`; instances re-export these with the standard output names above.

## Summary

1. **Prefix:** `{creator}-{team}` for resource naming and tags.
2. **EC2 key name:** `{creator}-{team}`; stored in `ec2_key_name`, file at `keys/{ec2_key_name}.pem`.
3. **EC2/SSH outputs:** Always expose `ssh_command`, `instance_id`, and `public_ip` for instances that support SSH so the Web UI Connect flow works without errors.
4. **Variables:** Align with root and shared variable names; set values in `terraform.tfvars`.
5. **Modules:** Primary EC2 resource is `aws_instance.instance`; security-group uses `aws_security_group.main`.
