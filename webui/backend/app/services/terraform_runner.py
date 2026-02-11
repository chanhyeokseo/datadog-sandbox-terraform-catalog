import asyncio
import os
from typing import Optional, AsyncIterator, Dict, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

EXIT_SENTINEL_PREFIX = "__TF_EXIT__:"

from app.services.instance_discovery import get_resource_directory_map


class TerraformRunner:
    def __init__(self, terraform_dir: str):
        self.terraform_dir = Path(terraform_dir)
        self.instances_dir = self.terraform_dir / "instances"
        self._resource_dir_map: Optional[Dict[str, str]] = None

    def _get_resource_dir_map(self) -> Dict[str, str]:
        if self._resource_dir_map is None:
            self._resource_dir_map = get_resource_directory_map(self.instances_dir)
        return self._resource_dir_map

    def get_resource_directory(self, resource_id: str) -> Optional[Path]:
        dir_name = self._get_resource_dir_map().get(resource_id)
        if dir_name:
            return self.instances_dir / dir_name
        return None
    
    async def output(self, resource_id: Optional[str] = None, env_extra: Optional[Dict[str, str]] = None) -> tuple[bool, str]:
        working_dir = self.terraform_dir
        if resource_id:
            resource_dir = self.get_resource_directory(resource_id)
            if resource_dir and resource_dir.exists():
                working_dir = resource_dir
        return await self._run_command(["terraform", "output", "-json"], cwd=working_dir, env_extra=env_extra)

    async def state_list(self, resource_id: Optional[str] = None, env_extra: Optional[Dict[str, str]] = None) -> tuple[bool, str]:
        working_dir = self.terraform_dir
        if resource_id:
            resource_dir = self.get_resource_directory(resource_id)
            if resource_dir and resource_dir.exists():
                working_dir = resource_dir
        return await self._run_command(["terraform", "state", "list"], cwd=working_dir, env_extra=env_extra)
    
    def _build_env(self, env_extra: Optional[Dict[str, str]] = None) -> Optional[dict]:
        if not env_extra:
            return None
        return {**os.environ, **env_extra}

    async def _run_command(self, cmd: list[str], cwd: Optional[Path] = None, env_extra: Optional[Dict[str, str]] = None) -> tuple[bool, str]:
        if cwd is None:
            cwd = self.terraform_dir
        env = self._build_env(env_extra)
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd),
                env=env
            )
            
            stdout, stderr = await process.communicate()
            
            output = stdout.decode() if stdout else ""
            error = stderr.decode() if stderr else ""
            
            full_output = output + error
            
            success = process.returncode == 0
            
            return success, full_output
            
        except Exception as e:
            logger.error(f"Error running terraform command: {e}")
            return False, str(e)
    
    async def ensure_terraform_init(self, resource_dir: Path, env_extra: Optional[Dict[str, str]] = None) -> tuple[bool, str]:
        terraform_dir = resource_dir / ".terraform"
        if terraform_dir.exists():
            return True, "Already initialized"
        env = self._build_env(env_extra)
        try:
            logger.debug(f"Running terraform init in {resource_dir}")
            process = await asyncio.create_subprocess_exec(
                "terraform", "init", "-no-color",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(resource_dir),
                env=env
            )
            
            stdout, stderr = await process.communicate()
            output = stdout.decode() + stderr.decode()
            
            if process.returncode == 0:
                logger.info(f"Successfully initialized terraform in {resource_dir}")
                return True, output
            else:
                logger.error(f"Failed to initialize terraform in {resource_dir}: {output}")
                return False, output
                
        except Exception as e:
            logger.error(f"Error running terraform init: {e}")
            return False, str(e)
    
    async def stream_apply(self, resource_id: str, auto_approve: bool = False, var_files: Optional[List[str]] = None, skip_init: bool = False, env_extra: Optional[Dict[str, str]] = None) -> AsyncIterator[str]:
        """Stream terraform apply for a specific resource directory"""
        resource_dir = self.get_resource_directory(resource_id)
        
        if not resource_dir:
            yield f"Error: Unknown resource ID: {resource_id}\n"
            yield f"{EXIT_SENTINEL_PREFIX}1\n"
            return

        if not resource_dir.exists():
            yield f"Error: Resource directory not found: {resource_dir}\n"
            yield f"{EXIT_SENTINEL_PREFIX}1\n"
            return

        if skip_init:
            yield f"Skipping initialization (resource already initialized from browser cache)\n"
        else:
            yield f"Checking terraform initialization in: {resource_dir}\n"
            init_success, init_output = await self.ensure_terraform_init(resource_dir, env_extra=env_extra)

            if not init_success:
                yield f"Error: Failed to initialize terraform\n{init_output}\n"
                yield f"{EXIT_SENTINEL_PREFIX}1\n"
                return

            if "Already initialized" not in init_output:
                yield f"Initialized terraform:\n{init_output}\n"
            else:
                yield f"✓ Resource is already initialized\n"

        cmd = ["terraform", "apply", "-no-color"]

        if var_files:
            for f in var_files:
                cmd.extend(["-var-file", f])
        if auto_approve:
            cmd.append("-auto-approve")

        env = self._build_env(env_extra)
        try:
            yield f"Applying terraform in: {resource_dir}\n"
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(resource_dir),
                env=env
            )

            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                yield line.decode()

            code = (await process.wait()) or 0
            yield f"{EXIT_SENTINEL_PREFIX}{0 if code == 0 else 1}\n"
        except Exception as e:
            logger.error(f"Error streaming terraform apply: {e}")
            yield f"Error: {str(e)}\n"
            yield f"{EXIT_SENTINEL_PREFIX}1\n"
    
    async def stream_destroy(self, resource_id: str, auto_approve: bool = False, var_files: Optional[List[str]] = None, skip_init: bool = False, env_extra: Optional[Dict[str, str]] = None) -> AsyncIterator[str]:
        """Stream terraform destroy for a specific resource directory"""
        resource_dir = self.get_resource_directory(resource_id)
        
        if not resource_dir:
            yield f"Error: Unknown resource ID: {resource_id}\n"
            yield f"{EXIT_SENTINEL_PREFIX}1\n"
            return

        if not resource_dir.exists():
            yield f"Error: Resource directory not found: {resource_dir}\n"
            yield f"{EXIT_SENTINEL_PREFIX}1\n"
            return

        if skip_init:
            yield f"Skipping initialization (resource already initialized from browser cache)\n"
        else:
            yield f"Checking terraform initialization in: {resource_dir}\n"
            init_success, init_output = await self.ensure_terraform_init(resource_dir, env_extra=env_extra)

            if not init_success:
                yield f"Error: Failed to initialize terraform\n{init_output}\n"
                yield f"{EXIT_SENTINEL_PREFIX}1\n"
                return

            if "Already initialized" not in init_output:
                yield f"Initialized terraform:\n{init_output}\n"
            else:
                yield f"✓ Resource is already initialized\n"

        cmd = ["terraform", "destroy", "-no-color"]

        if var_files:
            for f in var_files:
                cmd.extend(["-var-file", f])
        if auto_approve:
            cmd.append("-auto-approve")

        env = self._build_env(env_extra)
        try:
            yield f"Destroying terraform in: {resource_dir}\n"
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(resource_dir),
                env=env
            )

            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                yield line.decode()

            code = (await process.wait()) or 0
            yield f"{EXIT_SENTINEL_PREFIX}{0 if code == 0 else 1}\n"
        except Exception as e:
            logger.error(f"Error streaming terraform destroy: {e}")
            yield f"Error: {str(e)}\n"
            yield f"{EXIT_SENTINEL_PREFIX}1\n"

    async def stream_plan(self, resource_id: str, var_files: Optional[List[str]] = None, skip_init: bool = False, env_extra: Optional[Dict[str, str]] = None) -> AsyncIterator[str]:
        """Stream terraform plan for a specific resource directory"""
        resource_dir = self.get_resource_directory(resource_id)

        if not resource_dir:
            yield f"Error: Unknown resource ID: {resource_id}\n"
            yield f"{EXIT_SENTINEL_PREFIX}1\n"
            return

        if not resource_dir.exists():
            yield f"Error: Resource directory not found: {resource_dir}\n"
            yield f"{EXIT_SENTINEL_PREFIX}1\n"
            return

        if skip_init:
            yield f"Skipping initialization (resource already initialized from browser cache)\n"
        else:
            yield f"Checking terraform initialization in: {resource_dir}\n"
            init_success, init_output = await self.ensure_terraform_init(resource_dir, env_extra=env_extra)

            if not init_success:
                yield f"Error: Failed to initialize terraform\n{init_output}\n"
                yield f"{EXIT_SENTINEL_PREFIX}1\n"
                return

            if "Already initialized" not in init_output:
                yield f"Initialized terraform:\n{init_output}\n"
            else:
                yield f"✓ Resource is already initialized\n"

        cmd = ["terraform", "plan", "-no-color", "-lock=false", "-compact-warnings"]

        if var_files:
            for f in var_files:
                cmd.extend(["-var-file", f])

        env = self._build_env(env_extra)
        try:
            yield f"Planning terraform in: {resource_dir}\n"
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(resource_dir),
                env=env
            )

            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                yield line.decode()

            code = (await process.wait()) or 0
            yield f"{EXIT_SENTINEL_PREFIX}{0 if code == 0 else 1}\n"
        except Exception as e:
            logger.error(f"Error streaming terraform plan: {e}")
            yield f"Error: {str(e)}\n"
            yield f"{EXIT_SENTINEL_PREFIX}1\n"
