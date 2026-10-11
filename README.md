# Savora — Explainable Neuro-Symbolic Meal Planning (GC1 Monorepo)

Read [`AGENTS.md`](./AGENTS.md) and [`ARCHITECTURE.md`](./ARCHITECTURE.md) before making changes.

## Monorepo Layout

```text
.
├── AGENTS.md                 # Engineering rules & invariants
├── ARCHITECTURE.md           # System architecture & ownership
├── .agents/                  # Agent skills (supabase, supabase-postgres-best-practices) & designs
├── pyproject.toml            # uv workspace root (Python)
├── uv.lock                   # Locked Python dependencies
├── pnpm-workspace.yaml       # pnpm workspace root (JS/TS)
├── package.json              # Root JS scripts
├── pnpm-lock.yaml            # Locked JS dependencies
├── docker-compose.yml        # Optional local PostgreSQL 18 fallback
├── Makefile                  # Common developer commands
├── apps/
│   ├── frontend/             # Next.js 16 App Router + TypeScript + Tailwind v4
│   ├── backend/              # FastAPI + Pydantic v2 + async SQLAlchemy 2 + Alembic
│   └── ai_system/            # Importable Python AI package (savora_ai)
├── packages/
│   └── contracts/            # OpenAPI schemas & generated TypeScript types (@savora/contracts)
└── docs/                     # ADRs and evaluation notes
```

## Prerequisites

- **Python** `>=3.12` (managed via [`uv`](https://docs.astral.sh/uv/))
- **Node.js** `>=22` and [`pnpm`](https://pnpm.io/)
- **Supabase PostgreSQL** (`db.bgrlvhporhrmjsmgexay.supabase.co:5432`, or Docker for offline local Postgres)

## Quick Start

1. **Copy environment variables and set your Supabase database password:**
   ```bash
   cp .env.example .env
   # Replace [YOUR-PASSWORD] in .env (percent-encode special characters)
   ```
2. **Install dependencies:**
   ```bash
   make setup
   ```
3. **Run database migrations against Supabase PostgreSQL:**
   ```bash
   make migrate
   ```
4. **Start the development servers:**
   - Backend (`http://localhost:8000`): `make dev-backend`
   - Frontend (`http://localhost:3000`): `make dev-frontend`

## Checks

- **Tests:** `make test`
- **Lint (Ruff + ESLint):** `make lint`
- **Typecheck (Pyright + TypeScript):** `make typecheck`
- **Production Frontend Build:** `make build`
- **Export OpenAPI Schema:** `make contracts`

## Package Boundaries

- **Browser → Next.js (`apps/frontend`) → FastAPI (`apps/backend`) → AI (`apps/ai_system`).**
- `savora-backend` imports `savora-ai` in-process via the `uv` workspace; `savora-ai` never imports backend ORM models, controllers, or frontend code.
- PostgreSQL (Supabase) is the sole mandatory database for GC1.
