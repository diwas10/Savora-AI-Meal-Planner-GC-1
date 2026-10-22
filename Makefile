.PHONY: setup db dev dev-backend dev-frontend test lint typecheck migrate build contracts

setup:
	uv sync
	pnpm install

db:
	docker compose up -d postgres

dev:
	@echo "Run 'make db', then 'make dev-backend' and 'make dev-frontend' in separate terminals."

dev-backend:
	uv run uvicorn savora_backend.main:app --reload --port 8000

dev-frontend:
	pnpm dev

test:
	uv run pytest

lint:
	uv run ruff check .
	pnpm lint

typecheck:
	uv run pyright
	pnpm typecheck

migrate:
	uv run alembic -c apps/backend/alembic.ini upgrade head

build:
	pnpm build

contracts:
	uv run python -c "from savora_backend.contracts_gen import export_contracts; from savora_backend.main import app; export_contracts(openapi_spec=app.openapi())"
