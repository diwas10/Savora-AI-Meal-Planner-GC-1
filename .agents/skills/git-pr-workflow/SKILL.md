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
sh .tools/env.sh uv run ruff check .
sh .tools/env.sh uv run pyright
sh .tools/env.sh uv run pytest -q
sh .tools/env.sh pnpm lint
sh .tools/env.sh pnpm typecheck
sh .tools/env.sh pnpm build
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

## 4. Push Branch & Create Pull Request Directly from Terminal

1. Push the feature/fix branch to `origin`:
   ```bash
   git push -u origin <branch-name>
   ```
2. **Create the Pull Request directly from the terminal** using the local `gh` CLI (never ask the user to manually click a compare link on GitHub):
   ```bash
   sh .tools/env.sh gh pr create --base main --title "[ADD]: <summary>" --body "<PR description>"
   ```
3. Check the CI and PR Code Reviewer status runs:
   ```bash
   sh .tools/env.sh gh pr checks
   ```
4. **Never merge the PR into `main` yourself** unless the user explicitly asks you to merge it.
