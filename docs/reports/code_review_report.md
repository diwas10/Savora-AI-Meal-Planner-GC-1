# Code review report: Member 1 branch `feat/m1-nutrition-targets`

- **Date:** 19 Oct 2026
- **Scope:** every Member 1 file changed against `origin/main` (55 files: food data
  pipeline, meal composition, nutrition targets, recommendation, explanations, Member 2
  adapter, tests, curated data).
- **Method:** a structured high-effort review (the `code-review` skill), followed by a
  check of each finding against the committed export, then fixes. Every fix has a
  regression test. Two further bugs were found while writing tests and are listed in
  section 3.

## 1. Findings and fixes

| # | Severity | Finding | Real impact | Fix | Regression test |
|---|---|---|---|---|---|
| 1 | High | The planning explanation said "kept the day within the constraints" even for INFEASIBLE, TIMEOUT and INSUFFICIENT_DATA | A user would be told a sodium limit was met when no plan existed | one message per outcome; only FEASIBLE claims the constraints were met | `test_only_a_feasible_plan_claims_the_constraints_were_met` (3 outcomes) |
| 2 | High | The breakfast stratum accepted mains also tagged breakfast (REQUIRES_ACCOMPANIMENT), but no breakfast template can use them | **Confirmed in the export:** 9 breakfast slots wasted (e.g. "huevos rancheros", "thai spiced sausages") | the breakfast stratum requires COMPLETE_MEAL | `test_breakfast_stratum_needs_a_stand_alone_breakfast_dish` |
| 3 | High | When the model knew the history but none of the candidates, ranking ordered by ID under the model's name with no fallback reason | An arbitrary order shown as "personalised" | explicit `CANDIDATES_UNKNOWN_TO_MODEL` fallback; partially unscored candidates listed in `unscoredCandidates` and ordered by popularity | `test_model_that_scores_no_candidate_falls_back_explicitly`, `test_unscored_candidates_are_listed_and_ordered_by_popularity` |
| 4 | Medium | A pairing whose dishes share no meal type crashed `compose()` with a validation error | Latent: a curated override could abort the whole build | skipped and counted (`skippedNoCommonMealType`) | `test_pairing_without_a_common_meal_is_skipped_not_a_crash` |
| 5 | Medium | The composer chose its logic by slot *name* and presets knew 7 hard-coded names; a valid new template crashed mid-build | Latent: adding a template broke the build | dispatch on slot *roles*; templates reject unsupported shapes and unknown slot names when they load | `test_unsupported_template_shapes_fail_at_load` (2 cases) |
| 6 | Medium | Name words matched as substrings: "wrap" in "bacon-wrapped", "rice" in "licorice" | A main needing a staple was shown alone as a complete meal | whole-word match with optional plural (`has_name_word`) | `test_self_contained_name_words_match_whole_words_only` (5 cases) |
| 7 | Medium | Add-on overlap matched substrings: "apple" in "pineapple", "egg" in "eggplant" | Valid fruit and egg add-ons were dropped | whole-word token match with plural normalisation | `test_overlap_uses_whole_words` |
| 8 | Medium | Tiny heights or weights gave a negative Mifflin-St Jeor energy and an unexplained validation error | A 500/422 from the backend with no meaning | `TargetInput` accepts the adult range of the estimator (age 18-100, height 100-250 cm, weight 30-300 kg); explicit domain error | `test_inputs_outside_the_adult_estimator_range_are_rejected` (4 cases) |
| 9 | Low | The personalised explanation always said "blended with popularity", even for the pure model | A user-facing claim that was not always true | wording depends on the model version | `test_pure_model_ranking_does_not_claim_a_popularity_blend` |
| 10 | Low | `experiments.case_ranks` duplicated `dense_ranks`' ranking protocol | Two copies could silently diverge, so reports would use different protocols | one shared `scored_cases` generator and `rank_of` | `test_experiments_and_evaluation_share_one_ranking_protocol` |

Smaller findings, also fixed:

- `torch.load(..., weights_only=False)` changed to `weights_only=True` (no arbitrary
  unpickling of model files).
- The adapter compares enums, not their string values.
- `daily_request` passes the scenario through to its evidence.

## 2. Effect of the fixes on the data

Fixes 2, 6 and 7 change which dishes and meals the catalogue holds, so the export was
rebuilt and checked with `--check`:

| | Before | After |
|---|---|---|
| Catalogue dishes | 182 | 186 |
| Meals | 446 | 475 |
| Breakfast meals | 149 | **179** |
| Scenarios with enough meals for a week | 6 of 8 | **7 of 8** |

## 3. Bugs found by testing (not by the review)

| Bug | How found | Fix |
|---|---|---|
| `full_rank` raised `KeyError` when a history item was outside the ranking universe | the experiment smoke run (catalogue-restricted ranking) | history outside the universe is ignored; `test_history_outside_the_universe_is_ignored` |
| `case_ranks` called with weights (0.0, 0.0) appended every rank twice, doubling the case count | the new end-to-end experiment test; strict `zip` raised | weights are de-duplicated; `test_repeated_weights_do_not_duplicate_ranks` |
| The integration test used a fixed 1,500 mg cap that only fitted the old catalogue | rebuilding the export | the cap is now computed from the actual options (tightest feasible total and one below it) |

## 4. What the review checked and found sound

- Unknown nutrition never becomes zero (sum, scale, portion and adapter paths).
- Leakage: popularity, model training and hybrid-weight selection use training or
  validation data only; test is scored once.
- Determinism: the same seed reproduces training and evaluation exactly (seed 7 matched
  across two separate runs), and `--check` reproduces the export.
- The AI package imports no backend, ORM or HTTP code (CI boundary check).

## 5. Remaining known risks (not bugs)

- The Member 2 adapter labels real data SYNTHETIC because Member 2's contracts accept
  nothing else; it must not feed production.
- The model does not beat popularity on full-catalogue next-review prediction
  (`ranking_evaluation_report.md`).
- The curated lists need human confirmation.
