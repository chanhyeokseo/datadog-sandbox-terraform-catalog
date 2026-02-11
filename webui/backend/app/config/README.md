# Resource Configuration Management

## Overview

이 디렉토리는 리소스별 설정을 중앙집중식으로 관리합니다. 각 Terraform 리소스 타입에 대해 어떤 variables가 UI에 노출되어야 하는지 정의합니다.

## 파일 구조

```
config/
├── __init__.py           # 모듈 exports
├── resource_config.py    # 리소스 설정 정의
└── README.md            # 이 문서
```

## 주요 개념

### 1. Resource Variable Config

각 리소스 타입별로 UI에서 설정 가능한 variables를 정의합니다.

```python
ResourceVariableConfig(
    name="eks_enable_node_group",           # Variable 이름
    var_type=VariableType.BOOLEAN,          # 타입 (boolean, string, number, list)
    default_value=True,                     # 기본값
    description="Enable Linux node group"   # 설명
)
```

### 2. Common Variables

모든 리소스에서 공통으로 사용되는 variables (예: vpc_id, project_name 등)는 `COMMON_VARIABLES` 세트에 정의되어 Configurations 모달에서 관리됩니다.

### 3. Resource-Specific Variables

각 리소스 타입에 특화된 variables는 `RESOURCE_VARIABLE_CONFIGS` 딕셔너리에 정의됩니다.

## 사용 방법

### 새 리소스 타입 추가

1. `resource_config.py`의 `RESOURCE_VARIABLE_CONFIGS`에 새 항목 추가:

```python
RESOURCE_VARIABLE_CONFIGS = {
    # ... existing configs ...
    
    "your_resource_type": [
        ResourceVariableConfig(
            "your_var_name",
            VariableType.STRING,
            "default_value",
            "Description of the variable"
        ),
        # ... more variables ...
    ],
}
```

2. Terraform 파일에서 하드코딩된 값을 `var.your_var_name`으로 변경

3. `variables.tf`에 variable 정의 추가

4. `terraform.tfvars`에 기본값 추가

### 기존 리소스에 Variable 추가

1. `RESOURCE_VARIABLE_CONFIGS`의 해당 리소스에 `ResourceVariableConfig` 추가

2. Terraform 파일 수정 (하드코딩 → variable 참조)

3. `variables.tf`와 `terraform.tfvars` 업데이트

## 예시

### ECS 리소스 설정

**Before (하드코딩):**
```hcl
module "ecs_fargate" {
  source = "./modules/ecs"
  enable_fargate = true   # 하드코딩
  enable_ec2     = false  # 하드코딩
}
```

**After (설정 기반):**

1. `resource_config.py`:
```python
"ecs": [
    ResourceVariableConfig("ecs_enable_fargate", VariableType.BOOLEAN, True,
                          "Enable Fargate launch type for ECS"),
    ResourceVariableConfig("ecs_enable_ec2", VariableType.BOOLEAN, False,
                          "Enable EC2 launch type for ECS"),
]
```

2. Terraform 파일:
```hcl
module "ecs_fargate" {
  source = "./modules/ecs"
  enable_fargate = var.ecs_enable_fargate  # Variable 참조
  enable_ec2     = false
}
```

3. 이제 UI에서 `ecs_enable_fargate` 값을 동적으로 변경 가능!

## 장점

### ✅ 중앙집중식 관리
- 모든 리소스 설정을 한 곳에서 관리
- 변경사항 추적 용이

### ✅ 코드 일관성
- 모든 리소스가 동일한 패턴 사용
- 유지보수 쉬움

### ✅ 자동 UI 생성
- 설정 기반으로 UI 자동 생성
- 새 리소스 추가 시 UI 코드 수정 불필요

### ✅ 타입 안정성
- Variable 타입 명시
- 잘못된 값 입력 방지

## 함수 API

### `get_resource_variables(resource_type: str)`
특정 리소스 타입의 모든 variable 설정 반환

### `get_variable_names_for_resource(resource_type: str)`
특정 리소스 타입의 variable 이름 Set 반환

### `is_common_variable(var_name: str)`
Variable이 공통 variable인지 확인

## 유지보수 가이드

### Variable 추가 시
1. 설정 파일 업데이트
2. Terraform 파일 수정
3. variables.tf 업데이트
4. terraform.tfvars 업데이트
5. 테스트

### Variable 제거 시
1. 설정 파일에서 제거
2. Terraform 파일 확인
3. variables.tf에서 제거 (사용하지 않으면)
4. terraform.tfvars에서 제거

### Variable 타입 변경 시
1. 설정 파일의 타입 업데이트
2. variables.tf의 타입 업데이트
3. terraform.tfvars의 값 형식 확인
4. UI 테스트 (boolean ↔ string 변환 등)
