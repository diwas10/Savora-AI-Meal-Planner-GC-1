---
name: git-pr-workflow
description: >-
  Standard Git branching, pre-push verification, bracketed commit, and Pull Request
  workflow for Savora. Use whenever committing, pushing, or opening a PR.
---

# Savora Git & Pull Request Workflow

Follow these steps whenever preparing to commit or push changes in this repository.

## 1. Verify Branch (Never Commit to `main`)

1. Check the active branch:
   ```bash
   git branch --show-current
   ```
2. If on `main` (unless explicitly instructed by the user to push to `main`), create and switch to a new branch:
   - `feat/<scope>-<short-description>`
   - `fix/<scope>-<short-description>`
   - `refactor/<scope>-<short-description>`
   - `chore/<scope>-<short-description>`

## 2. Run Pre-Push Checks

Run the relevant checks and fix any errors before committing:

```bash
uv run ruff check .
uv run pyright
uv run pytest -q
pnpm lint
pnpm typecheck
pnpm build
```

If backend HTTP schemas changed, regenerate contracts:
```bash
make contracts
```

## 3. Stage & Commit with Bracketed Prefix

1. Inspect `git status -s` to ensure no secrets, `.env`, or build artifacts are staged.
2. Commit using one of the required prefixes (`[ADD]:`, `[UPDATE]:`, `[FIX]:`, `[REFACTOR]:`, `[DELETE]:`):
   ```bash
   git commit -m "[ADD]: <concise imperative summary>"
   ```

## 4. Push Branch & Open Pull Request

1. Push the feature/fix branch to `origin`:
   ```bash
   git push -u origin <branch-name>
   ```
2. Open a Pull Request against `main` (via `gh pr create --base main` if `gh` is authenticated, or share the compare URL `https://github.com/diwas10/Savora-AI-Meal-Planner-GC-1/compare/main...<branch-name>`).
3. **Never merge the PR into `main` yourself** unless the user explicitly asks you to merge it.
