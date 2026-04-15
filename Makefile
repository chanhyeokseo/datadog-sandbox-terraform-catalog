.PHONY: test-backend venv-backend
venv-backend:
	cd webui/backend && python3 -m venv .venv && .venv/bin/python -m pip install -r requirements-test.txt

test-backend:
	cd webui/backend && .venv/bin/python -m pytest tests/ -v
