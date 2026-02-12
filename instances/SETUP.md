# Instances

Each subdirectory is a Terraform configuration that can be applied independently via the Web UI.

1. Apply **shared** first (Web UI: security group). It creates the personal security group.
2. Add `security_group_ids = ["sg-xxxxx"]` to the root `terraform.tfvars`, using the shared output `security_group_id`.
3. Apply other instances from the Web UI as needed.
