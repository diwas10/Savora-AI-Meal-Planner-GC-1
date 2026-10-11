---
name: git-pr-workflow
description: >-
  Standard Git branching, pre-push verification, bracketed commit, and Pull Request
  workflow for Savora. Use whenever committing, pushing, or opening a PR.
---

# Savora Git & Pull Request Workflow

Follow these steps whenever preparing to commit, push, or open a Pull Request in this repository. This workflow applies to all contributors and AI coding agents.

## 1. Verify Branch (Never Commit to `main`)

1. Check the active branch:
   ```bash
   git branch --show-current
   ```
2. If on `main` (unless explicitly instructed by the user for a hotfix), create and switch to a descriptive branch:
   - `feat/<scope>-<short-description>`
   - `fix/<scope>-<short-description>`
   - `refactor/<scope>-<short-description>`
   - `chore/<scope>-<short-description>`

## 2. Run Pre-Push Checks

Run the workspace checks locally and fix any errors before committing:

```bash
uv run ruff check .
uv run pyright
uv run pytest -q
pnpm lint
pnpm typecheck
pnpm build
```

If backend HTTP DTOs or routes changed, regenerate contracts:
```bash
make contracts
```

## 3. Stage & Commit with Bracketed Prefix

1. Inspect `git status -s` to ensure no secrets, `.env`, or build artifacts are staged.
2. Commit using one of the required prefixes (`[ADD]:`, `[UPDATE]:`, `[FIX]:`, `[REFACTOR]:`, `[DELETE]:`):
   ```bash
   git commit -m "[ADD]: <concise imperative summary>"
   ```

## 4. Push Branch & Create a Well-Documented Pull Request

1. Push the feature/fix branch to `origin`:
   ```bash
   git push -u origin <branch-name>
   ```
2. **Write a complete, detailed PR description** following `.github/PULL_REQUEST_TEMPLATE.md`. Never create a PR with an empty body or unfilled HTML comments. Fill out every section:
   - `## Summary & Motivation`: What changed and why.
   - `## Architecture & Ownership`: Relevant `ARCHITECTURE.md` sections and checked `[x]` workspace boxes.
   - `## Key Changes`: Bulleted breakdown of modified modules/files.
   - `## Savora Invariants Checklist`: Checked `[x]` items confirming architectural boundaries, clinical/allergen safety invariants, contracts, and migrations.
   - `## Verification Executed`: Checked `[x]` commands that were run locally and their results.
3. Open (or update) the Pull Request against `main` using `gh`:
   ```bash
   gh pr create --base main --title "[ADD]: <summary>" --body-file <pr-body.md>
   ```
   *(If a PR is already open for the branch, update its title/description via `gh pr edit --title "..." --body-file <pr-body.md>`).*
4. Verify CI and PR Code Reviewer checks:
   ```bash
   gh pr checks
   ```
5. **Never merge the PR into `main` yourself** unless the user explicitly asks you to merge it.
