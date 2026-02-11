export enum ResourceType {
  EC2 = "ec2",
  RDS = "rds",
  EKS = "eks",
  ECS = "ecs",
  ECR = "ecr",
  LAMBDA = "lambda",
  DBM = "dbm",
  TEST = "test",
  SECURITY_GROUP = "security_group"
}

export enum ResourceStatus {
  ENABLED = "enabled",
  DISABLED = "disabled",
  UNKNOWN = "unknown"
}

export interface TerraformResource {
  id: string;
  name: string;
  type: ResourceType;
  file_path: string;
  line_start: number;
  line_end: number;
  status: ResourceStatus;
  description?: string;
}

export interface TerraformVariable {
  name: string;
  value?: string;
  description?: string;
  sensitive: boolean;
  is_common: boolean;  // True for global config variables
}

export interface TerraformStateResponse {
  resources: TerraformResource[];
  variables: TerraformVariable[];
}

export interface TerraformApplyRequest {
  resources: string[];
  auto_approve: boolean;
}

export interface ApiResponse {
  success: boolean;
  output?: string;
  error?: string;
  message?: string;
  command?: string;
}
