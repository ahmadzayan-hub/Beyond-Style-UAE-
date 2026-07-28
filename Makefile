# BSOS — make dev starts API on :8000 and UI on :5173.
# Windows users without make: run scripts/dev.ps1 (same behaviour).

PY := .venv/bin/python
PIP := .venv/bin/pip

.PHONY: setup dev api ui test audit verify-ledger backup migrate lock clean

setup:
	python3 -m venv .venv
	$(PIP) install -e '.[dev]'
	cd ui && npm install

dev:
	$(MAKE) -j2 api ui

api:
	$(PY) -m uvicorn bsos.api.app:app --reload --port 8000

ui:
	cd ui && npm run dev

test:
	$(PY) -m pytest tests/ -q

audit:
	$(PY) -m bsos.cli audit $(CONCEPT)

verify-ledger:
	$(PY) -m bsos.cli verify-ledger

backup:
	$(PY) -m bsos.cli backup

migrate:
	$(PY) -m alembic upgrade head

lock:
	.venv/bin/pip freeze --exclude-editable > requirements.lock

clean:
	rm -rf .venv ui/node_modules ui/dist var
