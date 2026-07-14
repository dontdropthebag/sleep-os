.PHONY: setup backend frontend dev seed test lint

setup:            ## install everything
	cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
	cd frontend && npm install

backend:          ## run API on :8000
	cd backend && .venv/bin/alembic upgrade head && .venv/bin/uvicorn app.main:app --reload --port 8000

frontend:         ## run UI on :3000
	cd frontend && npm run dev

dev:              ## run both (backend in background)
	(cd backend && .venv/bin/alembic upgrade head && .venv/bin/uvicorn app.main:app --port 8000 &) && cd frontend && npm run dev

seed:             ## load 35 nights of synthetic demo data
	cd backend && .venv/bin/python seed.py --reset

test:             ## run all tests
	cd backend && .venv/bin/python -m pytest tests -q
	cd frontend && npx vitest run

lint:             ## lint + typecheck
	cd backend && .venv/bin/ruff check app tests
	cd frontend && npx tsc --noEmit
