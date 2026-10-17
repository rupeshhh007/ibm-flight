PYTHON ?= python3

ifeq ($(OS),Windows_NT)
VENV_PY := backend/.venv/Scripts/python.exe
NPM := npm.cmd
else
VENV_PY := backend/.venv/bin/python
NPM := npm
endif

.PHONY: setup backend contracts contracts-check test check smoke

setup:
	$(PYTHON) -c "import sys; assert sys.version_info >= (3, 11), 'Python 3.11+ is required'; print(sys.version)"
	$(PYTHON) -m venv backend/.venv
	$(VENV_PY) -m pip install --upgrade pip
	$(VENV_PY) -m pip install -e "backend[test]"
	$(NPM) --prefix frontend ci

backend:
	$(VENV_PY) -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1

contracts:
	$(VENV_PY) scripts/export_contracts.py
	$(NPM) --prefix frontend run generate:api

contracts-check:
	$(VENV_PY) scripts/verify_contracts.py

test:
	$(VENV_PY) -m pytest backend/tests

check: contracts-check test
	$(NPM) --prefix frontend run typecheck

smoke:
	$(VENV_PY) scripts/smoke_test.py
