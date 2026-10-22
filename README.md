# Savora — Explainable Neuro-Symbolic Meal Planning (GC1 Monorepo)

Read [`AGENTS.md`](./AGENTS.md) and [`ARCHITECTURE.md`](./ARCHITECTURE.md) before making changes.
For the app's architecture, contracts, NLU evaluation, integration status and handoff notes, see [`docs/member3/HANDOFF.md`](./docs/member3/HANDOFF.md). The UI follows [`.agents/designs/DESIGN_SYSTEM.md`](./.agents/designs/DESIGN_SYSTEM.md) and [`.agents/designs/SCREENS.md`](./.agents/designs/SCREENS.md).

## Monorepo Layout

```text
.
├── AGENTS.md                 # Engineering rules & invariants
├── ARCHITECTURE.md           # System architecture & ownership
├── .agents/                  # Agent skills and the design docs (designs/DESIGN_SYSTEM.md, SCREENS.md)
├── pyproject.toml            # uv workspace root (Python)
├── uv.lock                   # Locked Python dependencies
├── pnpm-workspace.yaml       # pnpm workspace root (JS/TS)
├── package.json              # Root JS scripts
├── pnpm-lock.yaml            # Locked JS dependencies
├── docker-compose.yml        # Optional local PostgreSQL 18 fallback
├── Makefile                  # Common developer commands
├── apps/
│   ├── frontend/             # Next.js 16 App Router PWA + TypeScript + Tailwind v4
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
- **[Ollama](https://ollama.com)** for the local craving NLU model (optional: without it the
  deterministic parser is used and the app says so): `ollama pull qwen3:0.6b`

## Quick Start

1. **Configure Environment Variables (Mandatory — `.env` is gitignored):**
   ```bash
   cp .env.example .env
   # Fill in POSTGRES_HOST, POSTGRES_PASSWORD (percent-encoded), DATABASE_URL and
   # JWT_SECRET_KEY. Qwen defaults to local Ollama (QWEN_PROVIDER=ollama, qwen3:0.6b).
   # Set APP_ENV=production in deployments: the backend then refuses a weak JWT secret.
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
   - The frontend proxies `/api` to FastAPI (`BACKEND_URL`, default
     `http://localhost:8000`, read when the frontend is built or started), so the
     session is a first-party httpOnly cookie; no token is kept in `localStorage`.

## Install on a phone (PWA)

The service worker and offline support run in production builds only:

```bash
make build && pnpm --filter @savora/frontend start   # http://localhost:3000
```

Open the app over HTTPS (or `localhost`) on the phone. Android Chrome offers
**Install app**; on iPhone use Safari → Share → **Add to Home Screen**. The Profile tab also
shows an install card. Installed, Savora opens full-screen, keeps saved plans readable offline,
and needs a connection only to generate plans, swap meals and use Discover.

## Checks

- **Fast Unit & Integration Tests:** `uv run pytest -m "not slow"`
- **Backend on real PostgreSQL (opt-in, empty throwaway database):**
  `SAVORA_TEST_POSTGRES_URL=postgresql+asyncpg://... uv run pytest apps/backend/tests/test_postgres.py`
- **Full Test Suite (including weekly CSP solver tests):** `make test`
- **Craving NLU Evaluation (template, local Qwen, hybrid):** `uv run python -m savora_ai.evals.craving_nlu --model qwen3:0.6b`
- **Lint (Ruff + ESLint):** `make lint`
- **Typecheck (Pyright + TypeScript):** `make typecheck`
- **Production Frontend Build:** `make build`
- **Export OpenAPI Schema & Generate `@savora/contracts` Types:** `make contracts`

## Package Boundaries

- **Browser → Next.js (`apps/frontend`) → FastAPI (`apps/backend`) → AI (`apps/ai_system`).**
- `savora-backend` imports `savora-ai` in-process via the `uv` workspace; `savora-ai` never imports backend ORM models, controllers, or frontend code.
- PostgreSQL (Supabase) is the sole mandatory production database for GC1.
