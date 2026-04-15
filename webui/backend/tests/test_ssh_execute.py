import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.guardrails import GuardrailMiddleware


def _make_mock_pkey():
    return MagicMock()


def _build_app():
    with patch.dict("os.environ", {"TERRAFORM_DIR": "/tmp/fake-terraform"}):
        with patch("app.services.config_manager.ConfigManager"):
            with patch("app.services.key_manager.LocalKeyManager"):
                from app.routes.ssh import router
                _app = FastAPI()
                _app.add_middleware(GuardrailMiddleware)
                _app.include_router(router)
                return _app


@pytest.fixture
def app():
    return _build_app()


@pytest.fixture
def client(app):
    return TestClient(app)


class TestSSHExecuteSuccess:

    @patch("app.routes.ssh._load_pkey")
    @patch("app.routes.ssh._find_key_file", return_value="/tmp/key.pem")
    @patch("app.routes.ssh._resolve_key_path", return_value="/tmp/key.pem")
    def test_returns_stdout_stderr_exit_code(self, mock_resolve, mock_find, mock_pkey, client):
        mock_pkey.return_value = _make_mock_pkey()

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"hello world\n"
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        with patch("app.routes.ssh.paramiko.SSHClient") as MockSSH:
            instance = MockSSH.return_value
            instance.exec_command.return_value = (MagicMock(), mock_stdout, mock_stderr)

            resp = client.post("/api/ssh/execute", json={
                "hostname": "10.0.0.1",
                "command": "echo hello world",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["stdout"] == "hello world\n"
        assert data["stderr"] == ""
        assert data["exit_code"] == 0
        assert data["hostname"] == "10.0.0.1"

    @patch("app.routes.ssh._load_pkey")
    @patch("app.routes.ssh._find_key_file", return_value="/tmp/key.pem")
    @patch("app.routes.ssh._resolve_key_path", return_value="/tmp/key.pem")
    def test_nonzero_exit_code(self, mock_resolve, mock_find, mock_pkey, client):
        mock_pkey.return_value = _make_mock_pkey()

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b""
        mock_stdout.channel.recv_exit_status.return_value = 1
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b"command not found\n"

        with patch("app.routes.ssh.paramiko.SSHClient") as MockSSH:
            instance = MockSSH.return_value
            instance.exec_command.return_value = (MagicMock(), mock_stdout, mock_stderr)

            resp = client.post("/api/ssh/execute", json={
                "hostname": "10.0.0.1",
                "command": "badcmd",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["exit_code"] == 1
        assert "command not found" in data["stderr"]

    @patch("app.routes.ssh._load_pkey")
    @patch("app.routes.ssh._find_key_file", return_value="/tmp/key.pem")
    @patch("app.routes.ssh._resolve_key_path", return_value="/tmp/key.pem")
    def test_custom_username(self, mock_resolve, mock_find, mock_pkey, client):
        mock_pkey.return_value = _make_mock_pkey()

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"ok"
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        with patch("app.routes.ssh.paramiko.SSHClient") as MockSSH:
            instance = MockSSH.return_value
            instance.exec_command.return_value = (MagicMock(), mock_stdout, mock_stderr)

            resp = client.post("/api/ssh/execute", json={
                "hostname": "10.0.0.1",
                "command": "whoami",
                "username": "ubuntu",
            })

        assert resp.status_code == 200
        instance.connect.assert_called_once()
        call_kwargs = instance.connect.call_args[1]
        assert call_kwargs["username"] == "ubuntu"


class TestSSHExecuteErrors:

    @patch("app.routes.ssh._load_pkey", return_value=None)
    @patch("app.routes.ssh._find_key_file", return_value="/tmp/missing.pem")
    @patch("app.routes.ssh._resolve_key_path", return_value="/tmp/missing.pem")
    def test_no_key_returns_400(self, mock_resolve, mock_find, mock_pkey, client):
        resp = client.post("/api/ssh/execute", json={
            "hostname": "10.0.0.1",
            "command": "ls",
        })
        assert resp.status_code == 400
        assert "SSH key not found" in resp.json()["detail"]

    @patch("app.routes.ssh._load_pkey")
    @patch("app.routes.ssh._find_key_file", return_value="/tmp/key.pem")
    @patch("app.routes.ssh._resolve_key_path", return_value="/tmp/key.pem")
    def test_auth_failure_returns_401(self, mock_resolve, mock_find, mock_pkey, client):
        import paramiko
        mock_pkey.return_value = _make_mock_pkey()

        with patch("app.routes.ssh.paramiko.SSHClient") as MockSSH:
            instance = MockSSH.return_value
            instance.connect.side_effect = paramiko.AuthenticationException("bad key")

            resp = client.post("/api/ssh/execute", json={
                "hostname": "10.0.0.1",
                "command": "ls",
            })

        assert resp.status_code == 401
        assert "authentication failed" in resp.json()["detail"].lower()

    @patch("app.routes.ssh._load_pkey")
    @patch("app.routes.ssh._find_key_file", return_value="/tmp/key.pem")
    @patch("app.routes.ssh._resolve_key_path", return_value="/tmp/key.pem")
    def test_connection_error_returns_502(self, mock_resolve, mock_find, mock_pkey, client):
        mock_pkey.return_value = _make_mock_pkey()

        with patch("app.routes.ssh.paramiko.SSHClient") as MockSSH:
            instance = MockSSH.return_value
            instance.connect.side_effect = ConnectionRefusedError("refused")

            resp = client.post("/api/ssh/execute", json={
                "hostname": "10.0.0.1",
                "command": "ls",
            })

        assert resp.status_code == 502

    def test_missing_hostname_returns_422(self, client):
        resp = client.post("/api/ssh/execute", json={"command": "ls"})
        assert resp.status_code == 422

    def test_missing_command_returns_422(self, client):
        resp = client.post("/api/ssh/execute", json={"hostname": "10.0.0.1"})
        assert resp.status_code == 422
