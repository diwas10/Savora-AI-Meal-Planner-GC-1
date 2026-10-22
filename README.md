# Savora — Explainable Neuro-Symbolic Meal Planning (GC1 Monorepo)

Read [`AGENTS.md`](./AGENTS.md) and [`ARCHITECTURE.md`](./ARCHITECTURE.md) before making changes.
For Member 3 (Interaction) architecture, contracts, NLU evaluation, and handoff notes, see [`docs/member3/HANDOFF.md`](./docs/member3/HANDOFF.md).

## Monorepo Layout

```text
.
├── AGENTS.md                 # Engineering rules & invariants
├── ARCHITECTURE.md           # System architecture & ownership
├── .agents/                  # Shared team agent skills (supabase, supabase-postgres-best-practices)
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
└── docs/                     # ADRs, evaluation reports, and member handoff docs
```

## Prerequisites

- **Python** `>=3.12` (managed via [`uv`](https://docs.astral.sh/uv/))
- **Node.js** `>=22` and [`pnpm`](https://pnpm.io/)
- **Supabase PostgreSQL** (`db.<YOUR-SUPABASE-PROJECT-REF>.supabase.co:5432`, or Docker for offline local Postgres)

## Quick Start

1. **Configure Environment Variables (Mandatory — `.env` is gitignored):**
   ```bash
   cp .env.example .env
   # Fill in POSTGRES_HOST, POSTGRES_PASSWORD (percent-encoded), DATABASE_URL,
   # JWT_SECRET_KEY, and optionally QWEN_API_KEY / QWEN_BASE_URL / QWEN_MODEL_NAME in .env
   ```
2. **Install dependencies:**
   ```bash
   make setup
   ```
3. **Run database migrations against PostgreSQL:**
   ```bash
   make migrate
   ```
4. **Start the development servers:**
   - Backend (`http://localhost:8000`): `make dev-backend`
   - Frontend (`http://localhost:3000`): `make dev-frontend`

## Checks

- **Fast Unit & Integration Tests:** `uv run pytest -m "not slow"`
- **Full Test Suite (including weekly CSP solver tests):** `make test`
- **Craving NLU Evaluation Harness:** `uv run python -m savora_ai.evals.craving_nlu`
- **Lint (Ruff + ESLint):** `make lint`
- **Typecheck (Pyright + TypeScript):** `make typecheck`
- **Production Frontend Build:** `make build`
- **Export OpenAPI Schema & Generate `@savora/contracts` Types:** `make contracts`

## Package Boundaries

- **Browser → Next.js (`apps/frontend`) → FastAPI (`apps/backend`) → AI (`apps/ai_system`).**
- `savora-backend` imports `savora-ai` in-process via the `uv` workspace; `savora-ai` never imports backend ORM models, controllers, or frontend code.
- PostgreSQL (Supabase) is the sole mandatory production database for GC1.
