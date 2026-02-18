import asyncio
import shutil
import os
from typing import Optional, AsyncIterator, Dict, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

EXIT_SENTINEL_PREFIX = "__TF_EXIT__:"

from app.services.instance_discovery import get_resource_directory_map

_TF_WARMUP_CONFIG = (
    'terraform {\n'
    '  required_providers {\n'
    '    aws = {\n'
    '      source = "hashicorp/aws"\n'
    '    }\n'
    '  }\n'
    '}\n'
)


class TerraformRunner:
    def __init__(self, terraform_dir: str):
        self.terraform_dir = Path(terraform_dir)
        self.instances_dir = self.terraform_dir / "instances"
        self._resource_dir_map: Optional[Dict[str, str]] = None
        self._cache_ready = asyncio.Event()
        self._cache_warmup_started = False
        self._warmup_progress = 0
        self._warmup_message = ""

    def _is_provider_cached(self) -> bool:
        cache_dir = Path(os.environ.get("TF_PLUGIN_CACHE_DIR", ""))
        if not cache_dir.exists():
            return False
        aws_path = cache_dir / "registry.terraform.io" / "hashicorp" / "aws"
        return aws_path.exists() and any(aws_path.iterdir())

    def get_cache_status(self) -> dict:
        return {
            "ready": self._cache_ready.is_set(),
            "progress": self._warmup_progress,
            "message": self._warmup_message,
        }

    def _parse_warmup_line(self, line: str):
        text = line.strip()
        if "Initializing provider plugins" in text:
            self._warmup_progress = 10
            self._warmup_message = "Initializing provider plugins..."
        elif "Finding latest version" in text or "Finding hashicorp" in text:
            self._warmup_progress = 20
            self._warmup_message = text
        elif "Installing hashicorp" in text:
            self._warmup_progress = 40
            self._warmup_message = text
        elif "Installed hashicorp" in text:
            self._warmup_progress = 95
            self._warmup_message = text

    async def warmup_provider_cache(self):
        if self._cache_warmup_started:
            return
        self._cache_warmup_started = True

        if self._is_provider_cached():
            logger.info("Provider cache already warm, skipping download")
            self._warmup_progress = 100
            self._warmup_message = "Cached"
            self._cache_ready.set()
            return

        logger.info("Starting background provider cache warmup...")
        self._warmup_progress = 5
        self._warmup_message = "Starting provider download..."
        tmp_dir = Path("/tmp/tf-cache-warmup")
        try:
            tmp_dir.mkdir(parents=True, exist_ok=True)
            (tmp_dir / "main.tf").write_text(_TF_WARMUP_CONFIG)

            process = await asyncio.create_subprocess_exec(
                "terraform", "init", "-backend=false", "-input=false", "-no-color",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(tmp_dir)
            )

            while True:
                try:
                    line = await asyncio.wait_for(process.stdout.readline(), timeout=2.0)
                except asyncio.TimeoutError:
                    if 40 <= self._warmup_progress < 90:
                        self._warmup_progress = min(self._warmup_progress + 2, 90)
                    continue
                if not line:
                    break
                decoded = line.decode()
                self._parse_warmup_line(decoded)
                logger.debug(f"Cache warmup: {decoded.strip()}")

            await process.wait()
            if process.returncode == 0:
                self._warmup_progress = 100
                self._warmup_message = "Ready"
                logger.info("Provider cache warmup completed")
            else:
                logger.warning(f"Provider cache warmup failed (exit {process.returncode})")
        except Exception as e:
            logger.error(f"Provider cache warmup error: {e}")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            self._cache_ready.set()

    async def wait_for_cache(self):
        if not self._cache_warmup_started:
            return
        await self._cache_ready.wait()

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
        tf_dir = resource_dir / ".terraform"
        if tf_dir.exists():
            logger.debug(f"Terraform already initialized in {resource_dir}, skipping init")
            return True, "Already initialized"

        await self.wait_for_cache()
        env = self._build_env(env_extra)
        try:
            logger.debug(f"Running terraform init in {resource_dir}")
            process = await asyncio.create_subprocess_exec(
                "terraform", "init", "-no-color", "-input=false",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(resource_dir),
                env=env
            )

            lines = []
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                lines.append(line.decode())

            await process.wait()
            output = "".join(lines)

            if process.returncode == 0:
                logger.info(f"Successfully initialized terraform in {resource_dir}")
                return True, output
            else:
                logger.error(f"Failed to initialize terraform in {resource_dir}: {output}")
                return False, output

        except Exception as e:
            logger.error(f"Error running terraform init: {e}")
            return False, str(e)

    async def stream_init(self, resource_dir: Path, env_extra: Optional[Dict[str, str]] = None) -> AsyncIterator[str]:
        tf_dir = resource_dir / ".terraform"
        if tf_dir.exists():
            yield "Already initialized\n"
            return

        if self._cache_warmup_started and not self._cache_ready.is_set():
            yield "Waiting for AWS provider cache...\n"
            last_msg = ""
            while not self._cache_ready.is_set():
                if self._warmup_message and self._warmup_message != last_msg:
                    yield f"  {self._warmup_message}\n"
                    last_msg = self._warmup_message
                try:
                    await asyncio.wait_for(self._cache_ready.wait(), timeout=3.0)
                except asyncio.TimeoutError:
                    pass
            yield "Provider cache ready.\n\n"

        env = self._build_env(env_extra)
        try:
            process = await asyncio.create_subprocess_exec(
                "terraform", "init", "-no-color", "-input=false",
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
            if code != 0:
                yield f"{EXIT_SENTINEL_PREFIX}1\n"
        except Exception as e:
            logger.error(f"Error streaming terraform init: {e}")
            yield f"Error: {str(e)}\n"
            yield f"{EXIT_SENTINEL_PREFIX}1\n"
    
    async def stream_apply(self, resource_id: str, auto_approve: bool = False, var_files: Optional[List[str]] = None, env_extra: Optional[Dict[str, str]] = None) -> AsyncIterator[str]:
        resource_dir = self.get_resource_directory(resource_id)
        
        if not resource_dir:
            yield f"Error: Unknown resource ID: {resource_id}\n"
            yield f"{EXIT_SENTINEL_PREFIX}1\n"
            return

        if not resource_dir.exists():
            yield f"Error: Resource directory not found: {resource_dir}\n"
            yield f"{EXIT_SENTINEL_PREFIX}1\n"
            return

        init_failed = False
        async for line in self.stream_init(resource_dir, env_extra=env_extra):
            if line.startswith(EXIT_SENTINEL_PREFIX):
                init_failed = True
            yield line
        if init_failed:
            return

        cmd = ["terraform", "apply", "-no-color", "-input=false"]

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
    
    async def stream_destroy(self, resource_id: str, auto_approve: bool = False, var_files: Optional[List[str]] = None, env_extra: Optional[Dict[str, str]] = None) -> AsyncIterator[str]:
        resource_dir = self.get_resource_directory(resource_id)
        
        if not resource_dir:
            yield f"Error: Unknown resource ID: {resource_id}\n"
            yield f"{EXIT_SENTINEL_PREFIX}1\n"
            return

        if not resource_dir.exists():
            yield f"Error: Resource directory not found: {resource_dir}\n"
            yield f"{EXIT_SENTINEL_PREFIX}1\n"
            return

        init_failed = False
        async for line in self.stream_init(resource_dir, env_extra=env_extra):
            if line.startswith(EXIT_SENTINEL_PREFIX):
                init_failed = True
            yield line
        if init_failed:
            return

        cmd = ["terraform", "destroy", "-no-color", "-input=false"]

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

    async def force_unlock(self, resource_id: str, lock_id: str, env_extra: Optional[Dict[str, str]] = None) -> tuple[bool, str]:
        resource_dir = self.get_resource_directory(resource_id)
        if not resource_dir or not resource_dir.exists():
            return False, f"Resource directory not found: {resource_id}"
        init_ok, init_out = await self.ensure_terraform_init(resource_dir, env_extra=env_extra)
        if not init_ok:
            return False, f"Terraform init failed: {init_out}"
        return await self._run_command(
            ["terraform", "force-unlock", "-force", lock_id],
            cwd=resource_dir,
            env_extra=env_extra,
        )

    async def stream_plan(self, resource_id: str, var_files: Optional[List[str]] = None, env_extra: Optional[Dict[str, str]] = None) -> AsyncIterator[str]:
        resource_dir = self.get_resource_directory(resource_id)

        if not resource_dir:
            yield f"Error: Unknown resource ID: {resource_id}\n"
            yield f"{EXIT_SENTINEL_PREFIX}1\n"
            return

        if not resource_dir.exists():
            yield f"Error: Resource directory not found: {resource_dir}\n"
            yield f"{EXIT_SENTINEL_PREFIX}1\n"
            return

        init_failed = False
        async for line in self.stream_init(resource_dir, env_extra=env_extra):
            if line.startswith(EXIT_SENTINEL_PREFIX):
                init_failed = True
            yield line
        if init_failed:
            return

        cmd = ["terraform", "plan", "-no-color", "-input=false", "-lock=false", "-compact-warnings"]

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
