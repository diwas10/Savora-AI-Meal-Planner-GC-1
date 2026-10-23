# Source contribution verification — 23 October 2026

Baseline: `origin/main` at `c629270d34aca2745b41b12f51f2048b20e932d4`.
PR #23 was open and unmerged when preparing the isolated worktree.
Branch: `feat/sasrec-inference-handoff`.

| Check | Result |
| --- | --- |
| Service suite without checkpoint | 25 passed; 24 trained-checkpoint tests explicitly skipped |
| Service suite with external original checkpoint | 49 passed; no weights copied into this worktree |
| Existing ranking/evaluation regression suites | 30 passed |
| Repository Ruff | Passed (`ruff check . --no-cache`) |
| Repository Pyright | 0 errors, 0 warnings |
| Explicit service Pyright with CPU inference interpreter | 0 errors, 0 warnings |
| Python syntax/runtime imports | Passed for all service Python files |
| Remote source provenance | All eight runtime/build inputs match pinned HF revision byte-for-byte |
| Current health / missing app authentication | 200 ready with pinned digest / rank rejected with 401 |
| Staged secret/private-file, binary and large-file audit | Passed; no weights, credentials, raw datasets or local runtime paths |
| Git whitespace / architecture boundaries | Passed |

Service commands, from this directory with its isolated Python environment:

```sh
python -B -m pytest -c pytest.ini -q -p no:cacheprovider
# Repeat with SAVORA_TEST_CHECKPOINT_PATH set to the existing authorized artifact.
```

Application regression tests run from the repository root:

```sh
python -B -m pytest apps/ai_system/tests/test_ranking_api.py apps/ai_system/tests/test_recommendation_eval.py -q -p no:cacheprovider
```

The fresh worktree reused existing interpreters outside the worktree without
installing into the application environment. Pyright printed an environment-path
notice because this worktree has no `.venv`; the explicit `--pythonpath` supplied
the appropriate interpreter, and both type checks reported zero diagnostics.

The existing application source, public contracts, workspace manifests/lockfiles,
architecture rules and deployment configuration have zero diff against baseline.
Frontend lint/typecheck/build and the full application pytest suite were not rerun
for this isolated source archive. The new independent CI workflow runs the service
suite without model weights or credentials; normal repository CI remains intact.
No local Docker build was performed; a clone intentionally lacks its checkpoint.

The original private-gateway verification is retained as historical evidence.
Current read-only metadata reports **public** HF visibility, health is accessible
without a bearer, and rank still requires the application service token. No
visibility, credentials or infrastructure were changed. The content audit does
not claim a complete dependency CVE or training-data rights review.

Render integration remains unimplemented and unverified. See
[RENDER_HANDOFF.md](RENDER_HANDOFF.md) for Member 1's remaining work.
