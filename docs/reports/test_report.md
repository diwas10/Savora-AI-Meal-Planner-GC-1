# Test report (Member 1)

- **Date:** 19 Oct 2026
- **Branch:** `feat/m1-seed-dishes-model-delivery` (first written on `feat/m1-nutrition-targets`)
- **Environments:**
  - *Local:* macOS arm64, Python 3.14.8, with the optional `ml` extra (torch 2.14.1) and
    the raw datasets.
  - *CI-equivalent:* a fresh `uv sync --locked` environment with no torch, matching
    `.github/workflows/ci.yml`.

## 1. Results

| Check | Local (with torch) | CI-equivalent (no torch) |
|---|---|---|
| `ruff check` | passed (`apps`) | passed (whole repository, as CI runs it) |
| `ruff format --check apps` | 130 files formatted | - |
| `pyright` | 0 errors | 0 errors |
| AI boundary check (no backend, FastAPI or SQLAlchemy imports in `ai_system`) | - | passed |
| **`pytest`, whole repository** | **3,933 passed** in 6 min 37 s | **3,917 passed, 6 skipped** in 6 min 33 s |
| `build_catalogue --check` (export is reproducible) | up to date | needs raw data (local only) |

The 6 CI skips are exactly the torch-dependent test files and tests
(`test_torch_model.py`, `test_trained_model.py`, 3 tests in
`test_evaluation_runners.py`, 1 in `test_model_store.py`), skipped by
`pytest.importorskip`.

## 2. Member 1 test inventory (344 tests)

| Area | File | Tests | What it protects |
|---|---|---|---|
| Food.com rows | `test_food_catalogue.py` | 44 | quarantine reasons, energy rounding gap, timestamp versions, build report, CLI, `--check` |
| Classification | `test_food_classification.py` | 38 | course vs ingredient tags, dish class, review rules, overrides, whole-word names |
| Curation | `test_food_curation.py` | 7 | Nepali curation, cuisine vocabulary, pairing validation |
| Popularity | `test_food_popularity.py` | 8 | training cutoff only, cutoff day held out, multi-line reviews |
| Portions | `test_food_portions.py` | 8 | no invented grams, real USDA masses, absolute vectors |
| Selection | `test_food_selection.py` | 9 | determinism, quotas, vegetarian share, curated first, shortfalls reported, breakfast rule |
| USDA staples | `test_usda_staples.py` | 15 | identity guard, portion pinning, unknown vs zero, stale extract, unsalted rice |
| Cuisine tags | `test_foodcom_cuisines.py` | 23 | exact-tag cuisine mapping (EDA) |
| Composition | `test_meal_composition.py` | 17 | templates, pairings, presets, bounds, overlaps, unsupported shapes |
| Meal nutrition | `test_combination_nutrition.py` | 10 | unknown propagation, weakest tier, recomputation, energy range, preset intent, portion fields match the option |
| Coverage | `test_meal_coverage.py` | 6 | repetition maths, fail-closed proxy, whole-word exclusions |
| Explanations | `test_explanations.py` | 11 | every stage explained, honest wording, craving not budget-checked |
| Member 2 adapter | `test_member2_adapter_integration.py` | 4 | real export through Member 2's `solve_daily_plan`: feasible, tightest cap, infeasible |
| Evaluation | `test_recommendation_eval.py` | 16 | time split, metrics, exact full rank vs brute force (300 random cases) |
| Ranking API | `test_ranking_api.py` | 14 | only supplied IDs, explicit fallbacks, wire format, meal aggregation |
| Model | `test_torch_model.py` | 9 | training, zero ID vector for unseen items, no NaN, save/load, shared protocol, trimmed padding = padded, batched ranks = case-by-case count, validated hybrid weight saved, cached scorer = model, v1 checkpoint refused |
| Shipped model | `test_trained_model.py` | 3 | safe loading, determinism, content neighbours |
| Runners | `test_evaluation_runners.py` | 5 | `evaluate.run`, the experiment suite end to end, bootstrap, duplicate weights |
| Nutrition targets | `test_nutrition_models.py`, `test_nutrition_targets.py` | 34 | Mifflin-St Jeor, AMDR macros, protein RDA, adult input range |
| Enums | `test_enums.py` | 31 | wire tokens pinned |
| %DV verification | `test_dv_verification.py` | 5 | right table gives ratio 1.0; rounding and trace-nutrient skips; single-ingredient filter |
| Seed dishes | `test_seed_dishes.py` | 12 | only supplied Food.com anchors offered, cuisine interleave, preferred first, deterministic, 3-5 rule-safe picks, shipped catalogue gives 12 |
| Model delivery | `test_model_store.py` | 12 | manifest pins the shipped version and file, wrong file refused, download verified before rename, https only, `load_scorer` refuses a tampered file |
| Shortlist | `test_shortlist.py` | 4 | 2 meals x 4 presets per slot, meal-type filter, Member 2 budgets |
| Review sample | `test_review_export.py` | 3 | every total = sum of contributions; IDs; sugar unknown; never SYNTHETIC |

## 3. Coverage (Member 1 modules, Member 1 tests)

Measured with `coverage.py` (installed only for the run, so the lock file is unchanged)
over `core/food_data`, `core/meal_composition`, `core/recommendation`,
`core/explainability`, `core/nutrition` and `schemas/enums.py`.

**Total: 94% of 2,301 statements** (87% before the evaluation-runner tests). Measured
before `seeds.py` and `model_store.py` were added; not re-measured.

| Module | Cover | | Module | Cover |
|---|---|---|---|---|
| classification, selection, popularity, nutrition_convert | 100% | | ranking | 96% |
| baselines, metrics, coverage, api, nutrition models | 100% | | explanation | 96% |
| composer | 99% | | build_catalogue | 95% |
| member2_adapter, meal nutrition, sequences | 98% | | evaluate | 92% |
| portions, pairings | 97% | | experiments | 90% |
| | | | torch_model | 87% |
| | | | usda_staples | 85% |

The uncovered lines are mostly the command-line `main()` functions that need the raw
multi-gigabyte datasets (USDA extraction, model training). Those paths were run for real
to produce the committed extract, export and model.

## 4. Kinds of testing used

| Kind | Example |
|---|---|
| Unit | `classify`, `full_rank`, `sum_nutrients`, `step_portion` |
| Property / oracle | counted `full_rank` equals a brute-force sort on 300 random universes |
| Contract | pinned enum tokens; the ranking wire format; strict DTO validation |
| Data | the committed curated files load and agree (spec vs extract hash, pairings vs staples) |
| Regression | one test per code-review finding (`code_review_report.md`) |
| Integration | the real export through Member 2's daily CSP |
| End to end | the catalogue CLI with `--check`; the evaluation and experiment runners on tiny data |
| Behavioural (model) | content neighbours of Indian dishes are Indian more than 5x chance |
| Reproducibility | identical builds (`--check`), identical training for seed 7 |

## 5. How to reproduce

```
uv run ruff check . && uv run ruff format --check apps && uv run pyright
uv run pytest -q                                   # whole repository
cd apps/ai_system && uv run --extra ml pytest -q   # include torch tests
uv run python -m savora_ai.core.food_data.build_catalogue --source Data/Food.com/RAW_recipes.csv --check
```
