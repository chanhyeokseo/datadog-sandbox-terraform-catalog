import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

S3_PRESET_PREFIX = "eks-presets"
S3_LAYOUT_KEY = f"{S3_PRESET_PREFIX}/_layout.json"
S3_DEPLOYMENTS_KEY = f"{S3_PRESET_PREFIX}/_deployments.json"
OOTB_SOURCE_DIR = Path("/app/terraform-source/eks")


class EKSPresetManager:

    def __init__(self, terraform_dir: str):
        self.terraform_dir = Path(terraform_dir)
        self.eks_dir = self.terraform_dir / "eks"
        self._cached_s3_manager = None
        self._cache_initialized = False

    def _get_s3_manager(self):
        from app.services.s3_config_manager import S3ConfigManager
        bucket_name = self._get_s3_bucket_name()
        if not bucket_name:
            return None
        if self._cached_s3_manager is None or self._cached_s3_manager.bucket_name != bucket_name:
            self._cached_s3_manager = S3ConfigManager(bucket_name)
        return self._cached_s3_manager

    def _get_s3_bucket_name(self) -> Optional[str]:
        try:
            from app.services.config_manager import ConfigManager
            cm = ConfigManager()
            name_prefix = cm._get_name_prefix_from_tfvars()
            return cm.generate_bucket_name(name_prefix)
        except Exception as e:
            logger.debug(f"Could not determine S3 bucket name: {e}")
            return None

    def _read_manifest(self, preset_dir: Path) -> Optional[Dict]:
        manifest_path = preset_dir / "manifest.json"
        if not manifest_path.exists():
            return None
        try:
            return json.loads(manifest_path.read_text())
        except Exception as e:
            logger.warning(f"Failed to read manifest from {manifest_path}: {e}")
            return None

    def _is_ootb(self, name: str) -> Optional[bool]:
        if OOTB_SOURCE_DIR.is_dir():
            return (OOTB_SOURCE_DIR / name).is_dir()
        return None

    def _scan_local_presets(self) -> Dict[str, Dict]:
        presets = {}
        if not self.eks_dir.exists():
            return presets
        for d in sorted(self.eks_dir.iterdir()):
            if not d.is_dir() or d.name.startswith("_"):
                continue
            ootb = self._is_ootb(d.name)
            manifest = self._read_manifest(d)
            if manifest:
                manifest["built_in"] = ootb if ootb is not None else manifest.get("built_in", False)
                presets[d.name] = manifest
            else:
                files = [f.name for f in d.iterdir() if f.is_file() and f.name != "manifest.json"]
                presets[d.name] = {
                    "name": d.name,
                    "description": "",
                    "type": "kubectl",
                    "built_in": ootb if ootb is not None else False,
                    "deploy_commands": [],
                    "undeploy_commands": [],
                    "files": files,
                }
        return presets

    def _scan_s3_presets(self, force: bool = False) -> Dict[str, Dict]:
        if self._cache_initialized and not force:
            logger.debug("S3 preset scan skipped (local cache initialized)")
            return {}

        presets = {}
        s3 = self._get_s3_manager()
        if not s3:
            return presets
        try:
            keys = s3.list_files(f"{S3_PRESET_PREFIX}/")
            preset_names = set()
            for key in keys:
                parts = key.split("/")
                if len(parts) >= 2:
                    preset_names.add(parts[1])

            for name in sorted(preset_names):
                if not name or name.startswith("_"):
                    continue
                manifest_key = f"{S3_PRESET_PREFIX}/{name}/manifest.json"
                local_manifest = self.eks_dir / name / "manifest.json"
                local_manifest.parent.mkdir(parents=True, exist_ok=True)
                if s3.download_file(manifest_key, local_manifest):
                    manifest = self._read_manifest(local_manifest.parent)
                    if manifest:
                        presets[name] = manifest
                else:
                    file_keys = [k for k in keys if k.startswith(f"{S3_PRESET_PREFIX}/{name}/") and not k.endswith("/")]
                    files = [k.split("/", 2)[-1] if "/" in k.split("/", 2)[-1] else k.rsplit("/", 1)[-1] for k in file_keys]
                    files = [f.split("/")[-1] for f in files]
                    files = [f for f in files if f != "manifest.json"]
                    presets[name] = {
                        "name": name,
                        "description": "",
                        "type": "kubectl",
                        "built_in": False,
                        "deploy_commands": [],
                        "undeploy_commands": [],
                        "files": files,
                    }
        except Exception as e:
            logger.warning(f"Failed to scan S3 presets: {e}")
        return presets

    def list_presets(self) -> List[Dict]:
        local = self._scan_local_presets()
        s3_presets = self._scan_s3_presets()

        merged = dict(local)
        for name, preset in s3_presets.items():
            if name in merged:
                merged[name].update({k: v for k, v in preset.items() if k != "built_in"})
            else:
                preset["built_in"] = False
                merged[name] = preset

        return list(merged.values())

    def get_preset(self, name: str) -> Optional[Dict]:
        preset_dir = self.eks_dir / name
        manifest = self._read_manifest(preset_dir) if preset_dir.exists() else None

        if not manifest:
            s3 = self._get_s3_manager()
            if s3:
                manifest_key = f"{S3_PRESET_PREFIX}/{name}/manifest.json"
                local_manifest = preset_dir / "manifest.json"
                local_manifest.parent.mkdir(parents=True, exist_ok=True)
                if s3.download_file(manifest_key, local_manifest):
                    manifest = self._read_manifest(preset_dir)

        if not manifest:
            return None

        ootb = self._is_ootb(name)
        if ootb is not None:
            manifest["built_in"] = ootb
        else:
            manifest.setdefault("built_in", False)

        if "files" not in manifest or not manifest["files"]:
            files = []
            if preset_dir.exists():
                files = [f.name for f in preset_dir.iterdir() if f.is_file() and f.name != "manifest.json"]
            manifest["files"] = sorted(files)
        return manifest

    def get_preset_file(self, name: str, filename: str) -> Optional[str]:
        local_path = self.eks_dir / name / filename
        if local_path.exists():
            try:
                return local_path.read_text()
            except Exception as e:
                logger.warning(f"Failed to read local file {local_path}: {e}")

        s3 = self._get_s3_manager()
        if s3:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            s3_key = f"{S3_PRESET_PREFIX}/{name}/{filename}"
            if s3.download_file(s3_key, local_path):
                return local_path.read_text()

        return None

    def save_preset_file(self, name: str, filename: str, content: str) -> bool:
        preset_dir = self.eks_dir / name
        preset_dir.mkdir(parents=True, exist_ok=True)
        local_path = preset_dir / filename

        try:
            local_path.write_text(content)
            logger.debug(f"Saved preset file locally: {local_path}")
        except Exception as e:
            logger.error(f"Failed to write preset file {local_path}: {e}")
            return False

        s3 = self._get_s3_manager()
        if s3:
            s3_key = f"{S3_PRESET_PREFIX}/{name}/{filename}"
            s3.upload_file(local_path, s3_key)

        return True

    def save_preset(self, name: str, manifest: Dict) -> bool:
        preset_dir = self.eks_dir / name
        preset_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = preset_dir / "manifest.json"

        try:
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        except Exception as e:
            logger.error(f"Failed to write manifest {manifest_path}: {e}")
            return False

        s3 = self._get_s3_manager()
        if s3:
            s3_key = f"{S3_PRESET_PREFIX}/{name}/manifest.json"
            s3.upload_file(manifest_path, s3_key)

        return True

    def create_preset(self, name: str, description: str = "", preset_type: str = "kubectl",
                      deploy_commands: List[Dict] = None, update_commands: List[Dict] = None,
                      undeploy_commands: List[Dict] = None,
                      files: Dict[str, str] = None) -> bool:
        preset_dir = self.eks_dir / name
        if (preset_dir / "manifest.json").exists():
            logger.warning(f"Preset already exists: {name}")
            return False

        manifest = {
            "name": name,
            "description": description,
            "type": preset_type,
            "built_in": False,
            "deploy_commands": deploy_commands or [],
            "update_commands": update_commands or [],
            "undeploy_commands": undeploy_commands or [],
            "files": list((files or {}).keys()),
        }

        if not self.save_preset(name, manifest):
            return False

        for filename, content in (files or {}).items():
            self.save_preset_file(name, filename, content)

        return True

    def delete_preset(self, name: str) -> bool:
        preset = self.get_preset(name)
        if preset and preset.get("built_in"):
            logger.warning(f"Cannot delete built-in preset: {name}")
            return False

        preset_dir = self.eks_dir / name
        if preset_dir.exists():
            import shutil
            shutil.rmtree(preset_dir)
            logger.debug(f"Deleted local preset directory: {preset_dir}")

        s3 = self._get_s3_manager()
        if s3:
            keys = s3.list_files(f"{S3_PRESET_PREFIX}/{name}/")
            for key in keys:
                try:
                    s3.s3_client.delete_object(Bucket=s3.bucket_name, Key=key)
                    logger.debug(f"Deleted S3 key: {key}")
                except Exception as e:
                    logger.warning(f"Failed to delete S3 key {key}: {e}")

        return True

    def clone_preset(self, source_name: str, target_name: str) -> bool:
        source = self.get_preset(source_name)
        if not source:
            return False

        target_dir = self.eks_dir / target_name
        if (target_dir / "manifest.json").exists():
            logger.warning(f"Clone target already exists: {target_name}")
            return False

        manifest = dict(source)
        manifest["name"] = target_name
        manifest["built_in"] = False
        manifest["description"] = f"Cloned from {source_name}"
        file_list = manifest.pop("files", [])

        if not self.save_preset(target_name, {**manifest, "files": file_list}):
            return False

        for filename in file_list:
            content = self.get_preset_file(source_name, filename)
            if content is not None:
                self.save_preset_file(target_name, filename, content)

        return True

    def sync_preset_to_local(self, name: str) -> Optional[Path]:
        preset_dir = self.eks_dir / name
        preset_dir.mkdir(parents=True, exist_ok=True)

        if self._cache_initialized and preset_dir.exists() and any(preset_dir.iterdir()):
            logger.debug(f"Preset '{name}' already cached locally, skipping S3 sync")
            return preset_dir

        s3 = self._get_s3_manager()
        if s3:
            keys = s3.list_files(f"{S3_PRESET_PREFIX}/{name}/")
            for key in keys:
                filename = key.rsplit("/", 1)[-1]
                if not filename:
                    continue
                local_path = preset_dir / filename
                if local_path.exists():
                    logger.debug(f"Skipping already cached file: {local_path}")
                    continue
                s3.download_file(key, local_path)

        if preset_dir.exists() and any(preset_dir.iterdir()):
            return preset_dir
        return None

    def get_layout(self) -> List[Dict]:
        layout = None
        local_path = self.eks_dir / "_layout.json"

        if local_path.exists():
            try:
                layout = json.loads(local_path.read_text())
                logger.debug("Layout loaded from local cache")
            except Exception as e:
                logger.warning(f"Failed to parse local layout: {e}")

        if layout is None:
            s3 = self._get_s3_manager()
            if s3 and s3.download_file(S3_LAYOUT_KEY, local_path):
                try:
                    layout = json.loads(local_path.read_text())
                    logger.debug("Layout downloaded from S3")
                except Exception as e:
                    logger.warning(f"Failed to parse S3 layout: {e}")

        all_presets = {p["name"]: p for p in self.list_presets()}
        if layout is None:
            layout = self._build_default_layout(all_presets)
            self.save_layout(layout)
            return layout

        return self._sync_layout(layout, all_presets)

    def _build_default_layout(self, all_presets: Dict[str, Dict]) -> List[Dict]:
        ootb = [n for n, p in all_presets.items() if p.get("built_in")]
        custom = [n for n, p in all_presets.items() if not p.get("built_in")]
        layout: List[Dict] = []
        if ootb:
            layout.append({"id": "ootb", "type": "folder", "name": "ootb", "children": sorted(ootb)})
        for name in sorted(custom):
            layout.append({"id": name, "type": "preset"})
        return layout

    def _sync_layout(self, layout: List[Dict], all_presets: Dict[str, Dict]) -> List[Dict]:
        placed = set()
        for node in layout:
            if node["type"] == "folder":
                node["children"] = [c for c in node.get("children", []) if c in all_presets]
                placed.update(node["children"])
            else:
                placed.add(node["id"])
        layout = [n for n in layout if n["type"] == "folder" or n["id"] in all_presets]
        for name in all_presets:
            if name not in placed:
                layout.append({"id": name, "type": "preset"})
        return layout

    def save_layout(self, layout: List[Dict]) -> bool:
        s3 = self._get_s3_manager()
        if not s3:
            return False
        local_path = self.eks_dir / "_layout.json"
        local_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            local_path.write_text(json.dumps(layout, indent=2) + "\n")
            s3.upload_file(local_path, S3_LAYOUT_KEY)
            return True
        except Exception as e:
            logger.warning(f"Failed to save layout: {e}")
            return False

    def sync_preset_to_s3(self, name: str) -> bool:
        preset_dir = self.eks_dir / name
        if not preset_dir.exists():
            return False

        s3 = self._get_s3_manager()
        if not s3:
            return False

        success = True
        for f in preset_dir.iterdir():
            if not f.is_file():
                continue
            s3_key = f"{S3_PRESET_PREFIX}/{name}/{f.name}"
            if not s3.upload_file(f, s3_key):
                success = False
        return success

    def initialize_local_cache(self) -> None:
        s3 = self._get_s3_manager()
        if not s3:
            logger.warning("S3 not available, skipping EKS preset cache initialization")
            self._cache_initialized = True
            return

        self.eks_dir.mkdir(parents=True, exist_ok=True)

        try:
            local_path = self.eks_dir / "_layout.json"
            if s3.download_file(S3_LAYOUT_KEY, local_path):
                logger.debug("Cached _layout.json from S3")

            keys = s3.list_files(f"{S3_PRESET_PREFIX}/")
            downloaded = 0
            for key in keys:
                if key.endswith("/"):
                    continue
                rel = key[len(S3_PRESET_PREFIX) + 1:]
                if rel.startswith("_"):
                    continue
                local_file = self.eks_dir / rel
                local_file.parent.mkdir(parents=True, exist_ok=True)
                if s3.download_file(key, local_file):
                    downloaded += 1

            logger.info(f"EKS preset cache initialized: {downloaded} files downloaded from S3")
        except Exception as e:
            logger.warning(f"Failed to initialize EKS preset cache: {e}")

        self._cache_initialized = True

    def refresh_from_s3(self) -> None:
        logger.info("Refreshing EKS preset cache from S3")
        self._cache_initialized = False
        self.initialize_local_cache()

    def _deployments_path(self) -> Path:
        return self.eks_dir / "_deployments.json"

    def _read_deployments(self) -> Dict[str, Dict]:
        path = self._deployments_path()
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception as e:
                logger.warning(f"Failed to read deployments file: {e}")
        return {}

    def _save_deployments(self, data: Dict[str, Dict]) -> None:
        path = self._deployments_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n")
        s3 = self._get_s3_manager()
        if s3:
            s3.upload_file(path, S3_DEPLOYMENTS_KEY)

    def get_deployments(self) -> Dict[str, Dict]:
        local = self._read_deployments()
        if local:
            return local
        s3 = self._get_s3_manager()
        if s3:
            path = self._deployments_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            if s3.download_file(S3_DEPLOYMENTS_KEY, path):
                return self._read_deployments()
        return {}

    def mark_deployed(self, name: str) -> None:
        from datetime import datetime, timezone
        deployments = self._read_deployments()
        deployments[name] = {"deployed_at": datetime.now(timezone.utc).isoformat()}
        self._save_deployments(deployments)
        logger.debug(f"Marked preset as deployed: {name}")

    def mark_undeployed(self, name: str) -> None:
        deployments = self._read_deployments()
        if name in deployments:
            del deployments[name]
            self._save_deployments(deployments)
            logger.debug(f"Marked preset as undeployed: {name}")
