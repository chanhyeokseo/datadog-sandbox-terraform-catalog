from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from typing import Dict, List, Optional
import asyncio
import paramiko
import logging
import json
import os
from pathlib import Path
from io import StringIO

router = APIRouter(prefix="/api/ssh", tags=["ssh"])
logger = logging.getLogger(__name__)

TERRAFORM_DIR = os.environ.get("TERRAFORM_DIR", "/terraform")
active_connections: Dict[str, dict] = {}


def _terraform_root() -> Path:
    root = Path(TERRAFORM_DIR)
    if (root / "terraform.tfvars").exists():
        return root
    for candidate in [Path.cwd(), Path.cwd().parent, Path.cwd().parent.parent]:
        if (candidate / "terraform.tfvars").exists():
            return candidate
    return root


def _resolve_key_path(key_filename: Optional[str]) -> str:
    root = _terraform_root()
    k = (key_filename or "").strip()
    if k:
        return str(root / k) if not k.startswith("/") else k
    tfvars = root / "terraform.tfvars"
    if tfvars.exists():
        try:
            raw = tfvars.read_text(encoding="utf-8")
            for line in raw.splitlines():
                line = line.strip()
                if line.startswith("ec2_key_name") and "=" in line:
                    _, _, rest = line.partition("=")
                    val = rest.strip().strip('"').strip("'").strip()
                    if val:
                        return str(root / "keys" / f"{val}.pem")
        except Exception:
            pass
    return str(root / "keys" / "ec2-key.pem")


def _find_key_file(resolved_path: str) -> str:
    p = Path(resolved_path)
    if p.exists():
        return resolved_path
    name = p.name if p.suffix == ".pem" else f"{p.name}.pem"
    preferred_stem = p.stem
    roots = [Path(TERRAFORM_DIR), _terraform_root(), Path.cwd(), Path.cwd().parent, Path.cwd().parent.parent]
    bases = list(dict.fromkeys(r for r in roots if r))
    for base in bases:
        candidate = base / "keys" / name
        if candidate.exists():
            logger.debug("Using key from fallback path: %s", candidate)
            return str(candidate)
    for base in bases:
        keys_dir = base / "keys"
        if keys_dir.is_dir():
            pem_files = list(keys_dir.glob("*.pem"))
            if len(pem_files) == 1:
                logger.debug("Using single key found in %s: %s", keys_dir, pem_files[0])
                return str(pem_files[0])
            if pem_files:
                for f in pem_files:
                    if f.stem == preferred_stem:
                        return str(f)
                return str(pem_files[0])
    return resolved_path


def _load_pkey(key_path: str) -> Optional[paramiko.PKey]:
    path = Path(key_path)
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8")
    if "BEGIN RSA PRIVATE KEY" in raw:
        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.backends import default_backend
            key = serialization.load_pem_private_key(raw.encode(), password=None, backend=default_backend())
            openssh_bytes = key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.OpenSSH,
                encryption_algorithm=serialization.NoEncryption(),
            )
            return paramiko.RSAKey.from_private_key(StringIO(openssh_bytes.decode()))
        except Exception as e:
            logger.debug("RSA to OpenSSH conversion for SSH: %s", e)
    try:
        return paramiko.RSAKey.from_private_key_file(key_path)
    except paramiko.SSHException:
        try:
            return paramiko.Ed25519Key.from_private_key_file(key_path)
        except paramiko.SSHException:
            return None


@router.websocket("/connect/{connection_id}")
async def ssh_websocket(websocket: WebSocket, connection_id: str):
    await websocket.accept()
    
    try:
        init_data = await websocket.receive_text()
        params = json.loads(init_data)
        
        hostname = params.get('hostname')
        username = params.get('username', 'ec2-user')
        key_filename = params.get('key_filename')
        port = params.get('port', 22)
        key_path = _find_key_file(_resolve_key_path(key_filename))
        
        if not hostname:
            await websocket.send_text(json.dumps({
                'type': 'error',
                'data': 'Hostname is required'
            }))
            await websocket.close()
            return
        
        existing_connection = active_connections.get(connection_id)
        
        if existing_connection and 'channel' in existing_connection:
            logger.info(f"Reusing existing SSH session for {connection_id}")
            channel = existing_connection['channel']
            
            try:
                channel.send('\n')
                await websocket.send_text(json.dumps({
                    'type': 'connected',
                    'data': f'Reconnected to {username}@{hostname}'
                }))
            except Exception as e:
                logger.debug(f"Existing connection is dead, creating new one for {connection_id}: {e}")
                del active_connections[connection_id]
                existing_connection = None
        
        if not existing_connection:
            pkey = _load_pkey(key_path)
            if pkey is None:
                key_file = Path(key_path)
                if not key_file.exists():
                    await websocket.send_text(json.dumps({
                        'type': 'error',
                        'data': f'Key file not found: {key_path}. Ensure keys/ contains the .pem for ec2_key_name in terraform.tfvars, or create a key via Onboarding.'
                    }))
                    await websocket.close()
                    return
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            connect_kw = {"hostname": hostname, "port": port, "username": username, "timeout": 10}
            if pkey is not None:
                connect_kw["pkey"] = pkey
            else:
                connect_kw["key_filename"] = key_path
            try:
                await websocket.send_text(json.dumps({
                    'type': 'status',
                    'data': f'Connecting to {username}@{hostname}...'
                }))
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, lambda: ssh.connect(**connect_kw))
                
                channel = ssh.invoke_shell()
                channel.settimeout(0.0)
                
                active_connections[connection_id] = {
                    'ssh': ssh,
                    'channel': channel,
                    'hostname': hostname,
                    'username': username,
                    'websockets': []
                }
                
                await websocket.send_text(json.dumps({
                    'type': 'connected',
                    'data': f'Connected to {username}@{hostname}'
                }))
            except paramiko.AuthenticationException:
                await websocket.send_text(json.dumps({
                    'type': 'error',
                    'data': 'Authentication failed. Check your SSH key.'
                }))
                await websocket.close()
                return
            except paramiko.SSHException as e:
                await websocket.send_text(json.dumps({
                    'type': 'error',
                    'data': f'SSH error: {str(e)}'
                }))
                await websocket.close()
                return
            except Exception as e:
                await websocket.send_text(json.dumps({
                    'type': 'error',
                    'data': f'Connection error: {str(e)}'
                }))
                await websocket.close()
                return
        
        if 'websockets' not in active_connections[connection_id]:
            active_connections[connection_id]['websockets'] = []
        active_connections[connection_id]['websockets'].append(websocket)
        
        channel = active_connections[connection_id]['channel']
        
        async def read_from_channel():
            while True:
                try:
                    if channel.recv_ready():
                        data = channel.recv(4096)
                        if data:
                            for ws in active_connections[connection_id].get('websockets', []):
                                try:
                                    await ws.send_text(json.dumps({
                                        'type': 'output',
                                        'data': data.decode('utf-8', errors='ignore')
                                    }))
                                except Exception as e:
                                    logger.debug(f"Failed to send WebSocket output for connection {connection_id}: {e}")
                    else:
                        await asyncio.sleep(0.01)
                except Exception as e:
                    logger.error(f"Error reading from channel: {e}")
                    break
        
        async def write_to_channel():
            while True:
                try:
                    message = await websocket.receive_text()
                    msg_data = json.loads(message)
                    
                    if msg_data.get('type') == 'input':
                        input_data = msg_data.get('data', '')
                        channel.send(input_data)
                    elif msg_data.get('type') == 'resize':
                        cols = msg_data.get('cols', 80)
                        rows = msg_data.get('rows', 24)
                        channel.resize_pty(width=cols, height=rows)
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.error(f"Error writing to channel: {e}")
                    break
        
        await asyncio.gather(
            read_from_channel(),
            write_to_channel()
        )
        
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for {connection_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close()
    finally:
        if connection_id in active_connections:
            if 'websockets' in active_connections[connection_id]:
                try:
                    active_connections[connection_id]['websockets'].remove(websocket)
                    logger.info(f"Removed websocket from connection {connection_id}, remaining: {len(active_connections[connection_id]['websockets'])}")
                except ValueError:
                    pass


@router.get("/connections")
async def get_connections():
    connections = []
    for conn_id, conn_info in active_connections.items():
        connections.append({
            'id': conn_id,
            'hostname': conn_info.get('hostname'),
            'username': conn_info.get('username')
        })
    return {"connections": connections}


@router.delete("/connections/{connection_id}")
async def close_connection(connection_id: str):
    if connection_id in active_connections:
        conn = active_connections[connection_id]
        if 'channel' in conn:
            try:
                conn['channel'].close()
            except Exception:
                pass
        if 'ssh' in conn:
            try:
                conn['ssh'].close()
            except Exception:
                pass
        del active_connections[connection_id]
        logger.info(f"Closed connection {connection_id}")
        return {"success": True, "message": "Connection closed"}
    else:
        raise HTTPException(status_code=404, detail="Connection not found")
