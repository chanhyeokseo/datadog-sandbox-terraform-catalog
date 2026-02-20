import json
import logging
import os
import re
from typing import List, Dict, Optional
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
from app.models.schemas import TerraformResource, ResourceStatus, TerraformVariable
from app.config import get_variable_names_for_resource, is_common_variable, is_excluded_variable, get_ordered_common_variables, get_resource_only_variable_names, get_root_allowed_variable_names
from app.services.instance_discovery import (
    get_resource_id_for_instance,
    get_resource_type_from_dir,
    get_resource_directory_map,
)


class TerraformParser:
    def __init__(self, terraform_dir: str):
        self.terraform_dir = Path(terraform_dir)
        self.instances_dir = self.terraform_dir / "instances"
        self._config_manager = None
        self._s3_bucket_available: Optional[bool] = None
        self._cached_s3_manager = None

    @property
    def config_manager(self):
        """Lazy load config manager"""
        if self._config_manager is None:
            from app.services.config_manager import ConfigManager
            self._config_manager = ConfigManager(terraform_dir=str(self.terraform_dir))
        return self._config_manager

    def sync_to_parameter_store(self):
        """Sync root terraform.tfvars to Parameter Store - call this after onboarding is complete"""
        try:
            tfvars_path = self._root_tfvars_path()
            if not tfvars_path.exists():
                logger.warning("Root terraform.tfvars does not exist, cannot sync to Parameter Store")
                return False

            # Parse all variables from tfvars file
            variables = {}
            with open(tfvars_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        match = re.match(r'^(\w+)\s*=\s*(?:"([^"]*)"|(\S+))', line)
                        if match:
                            key = match.group(1)
                            value = (match.group(2) or match.group(3) or "").strip()
                            variables[key] = value

            if not variables:
                logger.warning("No variables found in terraform.tfvars")
                return False

            success = self.config_manager.save_config(variables)
            if not success:
                logger.error("Failed to save config to Parameter Store")
                return False

            logger.info(f"Synced {len(variables)} variables to Parameter Store")

            key_name = variables.get("ec2_key_name", "")
            if key_name:
                pem_path = self.terraform_dir / "keys" / f"{key_name}.pem"
                if pem_path.exists():
                    try:
                        pem_content = pem_path.read_text(encoding="utf-8")
                        self.config_manager.save_key(pem_content, key_name=key_name)
                    except Exception as e:
                        logger.warning(f"Failed to save key to Parameter Store during sync: {e}")

            return True

        except Exception as e:
            logger.error(f"Failed to sync to Parameter Store: {e}")
            return False
    
    def parse_all_resources(self) -> List[TerraformResource]:
        resources = []

        if not self.instances_dir.exists():
            return resources

        s3_statuses = self._fetch_all_s3_statuses()
        logger.debug("S3 status cache built: %s", {k: v.value for k, v in s3_statuses.items()})

        for instance_dir in sorted(self.instances_dir.iterdir()):
            if not instance_dir.is_dir():
                continue

            dir_name = instance_dir.name
            resource_type = get_resource_type_from_dir(dir_name)
            main_tf = instance_dir / "main.tf"
            if main_tf.exists():
                resource = self._parse_instance_directory(instance_dir, resource_type, s3_statuses)
                if resource:
                    resources.append(resource)

        return resources

    def _parse_instance_directory(self, instance_dir: Path, resource_type, s3_statuses: Dict[str, ResourceStatus] = None) -> Optional[TerraformResource]:
        main_tf = instance_dir / "main.tf"
        with open(main_tf, "r", encoding="utf-8") as f:
            lines = f.readlines()
        resource_id = get_resource_id_for_instance(instance_dir)
        module_name = resource_id

        if s3_statuses and instance_dir.name in s3_statuses:
            status = s3_statuses[instance_dir.name]
        else:
            status = self._check_resource_status_local(instance_dir)

        description = self._extract_description_from_directory(instance_dir)
        resource = TerraformResource(
            id=resource_id,
            name=module_name,
            type=resource_type,
            file_path=f"instances/{instance_dir.name}/main.tf",
            line_start=1,
            line_end=len(lines),
            status=status,
            description=description
        )

        return resource

    def _resolve_s3_bucket_name(self) -> Optional[str]:
        bucket = self._get_s3_bucket_name()
        if bucket:
            return bucket
        if not self.instances_dir.exists():
            return None
        for instance_dir in self.instances_dir.iterdir():
            if not instance_dir.is_dir():
                continue
            backend_tf = instance_dir / "backend.tf"
            if not backend_tf.exists():
                continue
            try:
                content = backend_tf.read_text(encoding="utf-8")
                match = re.search(r'bucket\s*=\s*"([^"]+)"', content)
                if match:
                    return match.group(1)
            except Exception:
                continue
        return None

    def _fetch_all_s3_statuses(self) -> Dict[str, ResourceStatus]:
        statuses: Dict[str, ResourceStatus] = {}
        if not self.instances_dir.exists():
            return statuses

        bucket_name = self._resolve_s3_bucket_name()
        if not bucket_name:
            logger.debug("Cannot determine S3 bucket name, skipping S3 status fetch")
            return statuses

        region = (os.environ.get("AWS_REGION") or "ap-northeast-2")
        try:
            s3_client = boto3.client("s3", region_name=region)
        except Exception as e:
            logger.warning("Failed to create S3 client for status check: %s", e)
            return statuses

        s3_state_keys: Dict[str, str] = {}
        try:
            paginator = s3_client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket_name, Prefix="instances/"):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    if key.endswith("/terraform.tfstate"):
                        parts = key.split("/")
                        if len(parts) == 3:
                            s3_state_keys[parts[1]] = key
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "NoSuchBucket":
                logger.debug("S3 bucket does not exist yet, skipping state check")
            else:
                logger.warning("Failed to list S3 state files: %s", e)
            return statuses
        except Exception as e:
            logger.warning("S3 status check failed (credentials expired?): %s", e)
            return statuses

        logger.debug("S3 state files found: %s", list(s3_state_keys.keys()))

        for instance_dir in sorted(self.instances_dir.iterdir()):
            if not instance_dir.is_dir() or not (instance_dir / "main.tf").exists():
                continue

            dir_name = instance_dir.name
            resource_id = get_resource_id_for_instance(instance_dir)

            s3_key = s3_state_keys.get(resource_id) or s3_state_keys.get(dir_name)

            if not s3_key:
                statuses[dir_name] = ResourceStatus.DISABLED
                logger.debug("S3 status: %s -> DISABLED (no state file)", dir_name)
                continue

            try:
                response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
                state_data = json.loads(response["Body"].read())
                resources = state_data.get("resources", [])
                actual_resources = [r for r in resources if r.get("mode") != "data"]
                if actual_resources:
                    statuses[dir_name] = ResourceStatus.ENABLED
                    logger.debug("S3 status: %s -> ENABLED (%d resources)", dir_name, len(actual_resources))
                else:
                    statuses[dir_name] = ResourceStatus.DISABLED
                    logger.debug("S3 status: %s -> DISABLED (empty state)", dir_name)
            except Exception as e:
                logger.debug("S3 status: %s -> DISABLED (error: %s)", dir_name, e)
                statuses[dir_name] = ResourceStatus.DISABLED

        return statuses

    def _check_resource_status_local(self, instance_dir: Path) -> ResourceStatus:
        tfstate_path = instance_dir / "terraform.tfstate"

        if not tfstate_path.exists():
            return ResourceStatus.DISABLED

        try:
            with open(tfstate_path, "r") as f:
                state_data = json.load(f)
            resources = state_data.get("resources", [])
            actual_resources = [r for r in resources if r.get("mode") != "data"]
            if actual_resources:
                return ResourceStatus.ENABLED
            return ResourceStatus.DISABLED
        except Exception:
            return ResourceStatus.DISABLED
    
    _UPPER_WORDS = {"ec2", "ecs", "ecr", "rds", "eks", "dbm", "ssh", "aws", "vpc", "iam", "alb", "nlb", "api", "ip", "rds"}

    def _smart_title(self, name: str) -> str:
        words = name.replace("-", " ").replace("_", " ").split()
        return " ".join(w.upper() if w.lower() in self._UPPER_WORDS else w.capitalize() for w in words)

    def _extract_description_from_directory(self, instance_dir: Path) -> Optional[str]:
        main_tf = instance_dir / "main.tf"
        if not main_tf.exists():
            return self._smart_title(instance_dir.name)
        with open(main_tf, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#"):
                    comment = line.lstrip("#").strip()
                    if comment and not comment.startswith("="):
                        return comment
        return self._smart_title(instance_dir.name)
    
    
    def get_aws_env(self) -> dict:
        result = {}

        tfvars_path = self._root_tfvars_path()
        if tfvars_path.exists():
            with open(tfvars_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        match = re.match(r'^(\w+)\s*=\s*(?:"([^"]*)"|(\S+))', line)
                        if match:
                            key = match.group(1)
                            value = (match.group(2) or match.group(3) or "").strip()
                            if key == "aws_access_key_id" and value:
                                result["AWS_ACCESS_KEY_ID"] = value
                            elif key == "aws_secret_access_key" and value:
                                result["AWS_SECRET_ACCESS_KEY"] = value
                            elif key == "aws_session_token" and value:
                                result["AWS_SESSION_TOKEN"] = value
                            elif key == "region" and value:
                                result["AWS_REGION"] = value

        for env_key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
                        "AWS_SESSION_TOKEN", "AWS_REGION", "AWS_PROFILE",
                        "AWS_SHARED_CREDENTIALS_FILE", "AWS_CONFIG_FILE"):
            val = os.environ.get(env_key)
            if val:
                result[env_key] = val

        if "AWS_REGION" not in result and tfvars_path.exists():
            with open(tfvars_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip().startswith("region"):
                        match = re.match(r'^region\s*=\s*(?:"([^"]*)"|(\S+))', line.strip())
                        if match:
                            result["AWS_REGION"] = (match.group(1) or match.group(2) or "").strip()
                            break

        return result

    def _unescape_tfvars_value(self, s: str) -> str:
        return s.replace("\\n", "\n").replace("\\r", "\r").replace('\\"', '"').replace("\\\\", "\\")

    def parse_variables(self) -> List[TerraformVariable]:
        file_map = {}
        tfvars_path = self._root_tfvars_path()
        if tfvars_path.exists():
            try:
                with open(tfvars_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        if '=' not in line:
                            continue
                        key_part, _, value_part = line.partition('=')
                        var_name = key_part.strip()
                        if not re.match(r'^\w+$', var_name):
                            continue
                        value_part = value_part.strip()
                        if value_part.startswith('"') and value_part.endswith('"'):
                            raw = value_part[1:-1]
                            try:
                                var_value = self._unescape_tfvars_value(raw)
                            except Exception:
                                var_value = raw
                        else:
                            var_value = value_part.split('#')[0].strip()
                        sensitive = any(k in var_name.lower() for k in ['password', 'key', 'secret', 'token'])
                        file_map[var_name] = (var_value, sensitive)
            except Exception:
                raise
        try:
            ordered = get_ordered_common_variables()
        except Exception:
            ordered = sorted(file_map.keys()) if file_map else []
        variables = []
        for var_name in ordered:
            sensitive = any(k in var_name.lower() for k in ['password', 'key', 'secret', 'token'])
            entry = file_map.get(var_name, ("", False))
            raw_value = entry[0]
            in_file = var_name in file_map
            display_value = "***" if (sensitive and in_file) else raw_value
            variables.append(TerraformVariable(
                name=var_name,
                value=display_value,
                sensitive=sensitive,
                is_common=True
            ))
        resource_only = get_resource_only_variable_names()
        for var_name in sorted(file_map.keys()):
            if var_name in resource_only:
                continue
            if not is_common_variable(var_name):
                entry = file_map.get(var_name, ("", False))
                raw_value, _ = entry
                sensitive = any(k in var_name.lower() for k in ['password', 'key', 'secret', 'token'])
                display_value = "***" if (sensitive and var_name in file_map) else raw_value
                variables.append(TerraformVariable(
                    name=var_name,
                    value=display_value,
                    sensitive=sensitive,
                    is_common=False
                ))
        return variables
    
    def get_resource_by_id(self, resource_id: str) -> Optional[TerraformResource]:
        resources = self.parse_all_resources()
        for resource in resources:
            if resource.id == resource_id:
                return resource
        for resource in resources:
            parts = resource.file_path.split("/")
            if len(parts) >= 2 and parts[1] == resource_id:
                return resource
        return None
    
    def get_resource_variables(self, resource_id: str) -> List[str]:
        """Get variables used by a specific resource"""
        resource = self.get_resource_by_id(resource_id)
        if not resource:
            return []
        
        configured_vars = get_variable_names_for_resource(resource.type.value, resource.id)
        
        # Parse variables.tf in the instance directory
        instance_dir_name = resource.file_path.split('/')[1]  # Extract dir name from path
        instance_dir = self.instances_dir / instance_dir_name
        variables_tf = instance_dir / "variables.tf"
        
        actual_vars = set()
        if variables_tf.exists():
            with open(variables_tf, 'r', encoding='utf-8') as f:
                content = f.read()
            
            var_pattern = re.compile(r'^variable\s+"(\w+)"\s*\{', re.MULTILINE)
            for match in var_pattern.finditer(content):
                var_name = match.group(1)
                if not is_excluded_variable(var_name):
                    actual_vars.add(var_name)
        
        all_vars = configured_vars | actual_vars
        
        return list(all_vars)
    
    def parse_instance_variable_defaults(self, resource_id: str) -> Dict[str, str]:
        instance_dir = self._get_instance_dir(resource_id)
        if not instance_dir:
            return {}
        variables_tf = instance_dir / "variables.tf"
        if not variables_tf.exists():
            return {}
        defaults: Dict[str, str] = {}
        content = variables_tf.read_text(encoding="utf-8")
        blocks = re.split(r'(?=^variable\s+")', content, flags=re.MULTILINE)
        for block in blocks:
            name_match = re.match(r'variable\s+"(\w+)"', block)
            if not name_match:
                continue
            var_name = name_match.group(1)
            default_match = re.search(r'default\s*=\s*"([^"]*)"', block)
            if default_match:
                defaults[var_name] = default_match.group(1)
                continue
            default_match = re.search(r'default\s*=\s*(true|false)\b', block)
            if default_match:
                defaults[var_name] = default_match.group(1)
                continue
            default_match = re.search(r'default\s*=\s*(\d+(?:\.\d+)?)\b', block)
            if default_match:
                defaults[var_name] = default_match.group(1)
        return defaults

    def _escape_tfvars_value(self, s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")

    def _get_instance_dir(self, resource_id: str) -> Optional[Path]:
        resource = self.get_resource_by_id(resource_id)
        if resource:
            parts = resource.file_path.split("/")
            if len(parts) >= 2:
                instance_dir = self.instances_dir / parts[1]
                if instance_dir.is_dir() and (instance_dir / "main.tf").exists():
                    return instance_dir
        if not self.instances_dir.exists():
            return None
        for d in self.instances_dir.iterdir():
            if not d.is_dir() or not (d / "main.tf").exists():
                continue
            if get_resource_id_for_instance(d) == resource_id:
                return d
            if d.name == resource_id or d.name == resource_id.replace("_", "-"):
                return d
        return None

    def _read_tfvars_to_map(self, tfvars_path: Path) -> Dict[str, str]:
        out = {}
        if not tfvars_path.exists():
            return out
        with open(tfvars_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key_part, _, value_part = line.partition("=")
                var_name = key_part.strip()
                if not re.match(r"^\w+$", var_name):
                    continue
                value_part = value_part.strip()
                if value_part.startswith('"') and value_part.endswith('"'):
                    raw = value_part[1:-1]
                    try:
                        out[var_name] = self._unescape_tfvars_value(raw)
                    except Exception:
                        out[var_name] = raw
                else:
                    out[var_name] = value_part.split("#")[0].strip()
        return out

    def get_instance_tfvars_map(self, resource_id: str) -> Dict[str, str]:
        instance_dir = self._get_instance_dir(resource_id)
        if not instance_dir:
            return {}
        return self._read_tfvars_to_map(instance_dir / "terraform.tfvars")

    def _root_tfvars_path(self) -> Path:
        return self.terraform_dir / "terraform.tfvars"

    def _instance_tfvars_path(self, resource_id: str) -> Optional[Path]:
        resource = self.get_resource_by_id(resource_id)
        if resource:
            parts = resource.file_path.split("/")
            if len(parts) >= 2:
                instance_dir = self.instances_dir / parts[1]
                if instance_dir.is_dir():
                    logger.debug("Resolved instance tfvars from file_path: resource_id=%s path=%s", resource_id, instance_dir / "terraform.tfvars")
                    return instance_dir / "terraform.tfvars"
        instance_dir = self._get_instance_dir(resource_id)
        if not instance_dir:
            return None
        return instance_dir / "terraform.tfvars"

    def _remove_variable_from_root(self, var_name: str) -> None:
        path = self._root_tfvars_path()
        if not path.exists():
            return
        var_pattern = re.compile(rf'^{re.escape(var_name)}\s*=')
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        new_lines = [line for line in lines if not var_pattern.match(line.strip())]
        if len(new_lines) != len(lines):
            logger.debug("Removing variable %s from root terraform.tfvars", var_name)
            with open(path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)

    def remove_non_common_from_root(self, var_name: str) -> None:
        if not is_common_variable(var_name):
            self._remove_variable_from_root(var_name)

    def _write_tfvars_line(self, tfvars_path: Path, var_name: str, var_value: str) -> bool:
        logger.debug("_write_tfvars_line: var=%s target=%s", var_name, tfvars_path.resolve())
        escaped = self._escape_tfvars_value(var_value)
        line_content = f'{var_name} = "{escaped}"\n'
        if not line_content.endswith('\n'):
            line_content += '\n'
        if not tfvars_path.exists():
            with open(tfvars_path, 'w', encoding='utf-8') as f:
                f.write(line_content)
            return True
        with open(tfvars_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            if line and not line.endswith('\n'):
                lines[i] = line + '\n'
        updated = False
        var_pattern = re.compile(rf'^{re.escape(var_name)}\s*=')
        for i, line in enumerate(lines):
            if var_pattern.match(line.strip()):
                lines[i] = line_content
                updated = True
                break
        if not updated:
            lines.append(line_content)
        with open(tfvars_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        return True

    def write_root_tfvars(self, var_name: str, var_value: str) -> bool:
        if var_name not in get_root_allowed_variable_names():
            logger.warning("Blocked write to root terraform.tfvars: var_name=%s not in allowed list", var_name)
            return False
        path = self._root_tfvars_path()
        logger.debug("write_root_tfvars: var=%s path=%s", var_name, path)
        success = self._write_tfvars_line(path, var_name, var_value)

        # Sync to S3 after successful write
        if success:
            self._sync_root_tfvars_to_s3()

        # Note: Parameter Store sync removed from here
        # Call sync_to_parameter_store() manually after onboarding is complete

        return success

    def _break_symlink_to_root(self, tfvars_path: Path) -> None:
        if not tfvars_path.is_symlink():
            return
        root_path = self._root_tfvars_path()
        if tfvars_path.resolve() != root_path.resolve():
            return
        logger.warning("Replacing symlink to root with independent file: %s", tfvars_path)
        content = ""
        if root_path.exists():
            content = self._filter_common_only_lines(root_path.read_text(encoding="utf-8"))
        tfvars_path.unlink()
        tfvars_path.write_text(content, encoding="utf-8")

    def write_tfvars_to_path(self, tfvars_path: Path, var_name: str, var_value: str) -> bool:
        root_path = self._root_tfvars_path()
        self._break_symlink_to_root(tfvars_path)
        if tfvars_path.resolve() == root_path.resolve():
            logger.warning("Blocked write to root terraform.tfvars: var_name=%s path=%s", var_name, tfvars_path)
            return False
        logger.debug("write_tfvars_to_path: var=%s path=%s", var_name, tfvars_path)
        return self._write_tfvars_line(tfvars_path, var_name, var_value)

    def write_instance_tfvars(self, resource_id: str, var_name: str, var_value: str) -> bool:
        path = self._instance_tfvars_path(resource_id)
        if path is None:
            logger.debug("write_instance_tfvars: no path for resource_id=%s", resource_id)
            return False
        self._break_symlink_to_root(path)
        root_path = self._root_tfvars_path()
        if path.resolve() == root_path.resolve():
            return False
        success = self._write_tfvars_line(path, var_name, var_value)

        # Sync to S3 after successful write
        if success:
            self._sync_instance_tfvars_to_s3(resource_id, path)

        return success

    def _filter_common_only_lines(self, content: str) -> str:
        from app.config import get_root_allowed_variable_names
        allowed = get_root_allowed_variable_names()
        out_lines = []
        for line in content.splitlines(keepends=True):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                out_lines.append(line)
                continue
            if "=" not in stripped:
                out_lines.append(line)
                continue
            key_part, _, _ = stripped.partition("=")
            var_name = key_part.strip()
            if re.match(r"^\w+$", var_name) and var_name not in allowed:
                logger.debug("Filtering out non-common variable from sync: %s", var_name)
                continue
            out_lines.append(line)
        return "".join(out_lines)

    def copy_root_tfvars_to_instances(self) -> bool:
        root_tfvars = self._root_tfvars_path()
        if not root_tfvars.exists():
            return False
        try:
            raw_content = root_tfvars.read_text(encoding="utf-8")
        except OSError:
            return False
        content = self._filter_common_only_lines(raw_content)
        dir_map = get_resource_directory_map(self.instances_dir)
        ok = False

        # Sync root tfvars to S3 first
        self._sync_root_tfvars_to_s3()

        for _resource_id, dir_name in dir_map.items():
            instance_dir = self.instances_dir / dir_name
            if not instance_dir.is_dir():
                continue
            dst = instance_dir / "terraform.tfvars"
            try:
                dst.write_text(content, encoding="utf-8")
                ok = True
                # Sync each instance tfvars to S3
                self._sync_instance_tfvars_to_s3(_resource_id, dst)
            except OSError:
                pass
        return ok

    def copy_root_tfvars_to_resource(self, resource_id: str) -> bool:
        root_tfvars = self._root_tfvars_path()
        instance_dir = self._get_instance_dir(resource_id)
        if not instance_dir:
            return False
        if root_tfvars.exists():
            try:
                raw_content = root_tfvars.read_text(encoding="utf-8")
                content = self._filter_common_only_lines(raw_content)
                (instance_dir / "terraform.tfvars").write_text(content, encoding="utf-8")
                return True
            except OSError:
                return False
        tfvars_path = instance_dir / "terraform.tfvars"
        if not tfvars_path.exists():
            return True
        try:
            tfvars_path.unlink()
            return True
        except OSError:
            return False

    def delete_instance_variables(self, resource_id: str) -> bool:
        instance_dir = self._get_instance_dir(resource_id)
        if not instance_dir:
            return False
        tfvars_path = instance_dir / "terraform.tfvars"
        if not tfvars_path.exists():
            return True
        try:
            tfvars_path.unlink()
            return True
        except OSError:
            return False

    def _get_s3_bucket_name(self) -> Optional[str]:
        try:
            name_prefix = self.config_manager._get_name_prefix_from_tfvars()
            return self.config_manager.generate_bucket_name(name_prefix)
        except Exception as e:
            logger.debug(f"Could not determine S3 bucket name: {e}")
            return None

    def _get_s3_manager(self):
        from app.services.s3_config_manager import S3ConfigManager
        bucket_name = self._get_s3_bucket_name()
        if not bucket_name:
            return None
        if self._cached_s3_manager is None or self._cached_s3_manager.bucket_name != bucket_name:
            self._cached_s3_manager = S3ConfigManager(bucket_name)
        return self._cached_s3_manager

    def mark_s3_available(self):
        self._s3_bucket_available = True

    def _sync_root_tfvars_to_s3(self) -> bool:
        if self._s3_bucket_available is False:
            return False
        try:
            s3_manager = self._get_s3_manager()
            if not s3_manager:
                return False
            success = s3_manager.upload_root_tfvars(self.terraform_dir)
            if success:
                self._s3_bucket_available = True
            elif self._s3_bucket_available is None:
                self._s3_bucket_available = False
            return success
        except Exception as e:
            logger.warning(f"Failed to sync root tfvars to S3: {e}")
            return False

    def _sync_instance_tfvars_to_s3(self, resource_id: str, tfvars_path: Path) -> bool:
        if self._s3_bucket_available is False:
            return False
        try:
            s3_manager = self._get_s3_manager()
            if not s3_manager:
                return False
            instance_dir = tfvars_path.parent
            instance_name = instance_dir.name
            success = s3_manager.upload_instance_tfvars(instance_dir, instance_name)
            if success:
                self._s3_bucket_available = True
            elif self._s3_bucket_available is None:
                self._s3_bucket_available = False
            return success
        except Exception as e:
            logger.warning(f"Failed to sync instance tfvars to S3: {e}")
            return False
