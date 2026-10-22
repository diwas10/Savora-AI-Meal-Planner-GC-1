# PR A final audit

Base/main: `b96d5a46c757b40a709b87262d09eed027b86cf4`.
Branch: `feat/member2-native-nutrients-review`.
Implementation commit: `2d93f02` (the documentation audit is a separate following commit).
Independent extraction: 19 implementation/test/handoff files; no unfinished swap envelope or
compact transport. See `pr_a_handoff.md` for protocol IDs, ownership and inactive/deferred work.

## Executed gates

- 197 passed: test_nutrients_v2.py, test_reviewed_knowledge.py,
  test_weekly_value_priority.py, test_real_integration_examples.py,
  test_member2_phase3_integration.py (includes dependency direction / cycle checks).
- 514 passed: test_weekly_search_v2_contracts.py, test_weekly_contracts.py,
  test_weekly_ordering.py; 1240.47 seconds, no skipped tests.
- 1 passed: test_real_catalogue_native.py on this independent main-based tree.
- **712 distinct repository tests passed**, zero failures/errors/skips.
- 27 passed: actual PR #19 `test_pipelines.py` from c5af633, with that branch's
  catalogue, food/pipeline code and this PR's reasoning/schema tree in an isolated overlay.
- 1 additional successful native test replay on that overlay's latest catalogue.
  An initial overlay collection attempt lacked the new eval helper; copying this PR's
  helper into the overlay corrected it before the successful replay.
- Ruff check of all AI source plus the five new test files passed; format check of
  all 16 changed/new Python files passed. Full configured Pyright: 0 errors/warnings.
- `git diff --check` passed. No frontend or full backend test/build was run: neither
  workspace nor HTTP/OpenAPI/generated TypeScript contracts changed.

The actual Member 1 call at planning.py:412 passes `reuse_preparation=True` and
`preparation_cache_entries=1`. Both parameters/defaults remain unchanged. This validates
call compatibility, not Member 1 activation of the new native/priority strategies.

## Historical compatibility

Fresh executions in PR A reproduce all archived-main wire SHA-256 values:

| Protocol | SHA-256 |
|---|---|
| weekly v1 | a4741e103f7f9fed44a7b82f3b95102db85368c642b780dd77c87515528c8985 |
| weekly v2 | 78a5be77d51ee796cdddbb5fddd7ad30b89cfa6249df6565867d1e0f2f49f89a |
| B1 | 80a0771469661c35e870b484af214e385c8e43df458b48453d308ae1233a28a1 |
| B2 | 993a3a6183f677c13c4f748f0ca818264808278bc3ee371a5bd8450682214061 |

Verification XML, logs, isolated Member 1 overlay and wire outputs are preserved in
the ignored `.delta/pr-a/` directory in the PR A worktree. The original six-commit
worktree and its historical measured-source archive remain untouched. No Phase 7.4
jobs were restarted; 624/3007 remains the historical checkpoint.

## Known limits and merge order

Knowledge releases remain review-only and clinical declarations inactive. Native
nutrient pruning, backend native/priority adapters, production canonical mappings and
clinical approval remain deferred. Preliminary timings are two pairs, no warmups,
no trained Transformer scorer and no significance/final-source latency claim.
PR A targets main; PR #19 can merge independently. PR B targets PR A because it imports
the native nutrient contracts. Member 1 retains runtime resolver, backend/persistence
and end-to-end ownership. Neither PR is clinical validation.

## Exact changed files (including audit/PR description)

- `apps/ai_system/src/savora_ai/core/reasoning/nutrients_v2.py`
- `apps/ai_system/src/savora_ai/core/reasoning/reviewed_knowledge.py`
- `apps/ai_system/src/savora_ai/core/reasoning/weekly_ordering.py`
- `apps/ai_system/src/savora_ai/core/reasoning/weekly_proof_v2.py`
- `apps/ai_system/src/savora_ai/core/reasoning/weekly_search_v2.py`
- `apps/ai_system/src/savora_ai/evals/real_catalogue_benchmarks.py`
- `apps/ai_system/src/savora_ai/evals/real_catalogue_inputs.py`
- `apps/ai_system/src/savora_ai/schemas/nutrients_v2.py`
- `apps/ai_system/src/savora_ai/schemas/reviewed_knowledge.py`
- `apps/ai_system/src/savora_ai/schemas/weekly_search_v2.py`
- `apps/ai_system/src/savora_ai/schemas/weekly_solver_v2.py`
- `apps/ai_system/tests/test_nutrients_v2.py`
- `apps/ai_system/tests/test_real_catalogue_native.py`
- `apps/ai_system/tests/test_real_integration_examples.py`
- `apps/ai_system/tests/test_reviewed_knowledge.py`
- `apps/ai_system/tests/test_weekly_value_priority.py`
- `docs/member2/clinical_evidence_inventory.md`
- `docs/member2/pr_a_audit.md`
- `docs/member2/pr_a_handoff.md`
- `docs/member2/pr_a_pull_request.md`
- `docs/member2/real_integration_examples.json`
