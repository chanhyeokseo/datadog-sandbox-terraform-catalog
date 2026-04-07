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
  is_shared?: boolean;
  shared_from?: string;
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

export interface EKSClusterInfo {
  name: string;
  arn: string;
  status: string;
  owner_prefix?: string;
}

export interface ClusterShareRequest {
  id: string;
  requester_prefix: string;
  cluster_name: string;
  cluster_arn: string;
  owner_prefix: string;
  status: 'pending' | 'approved' | 'denied';
  created_at: string;
  updated_at: string;
}

export interface SharedCluster {
  cluster_name: string;
  cluster_arn: string;
  owner_prefix: string;
  shared_at: string;
}
