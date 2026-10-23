# PR A: native nutrients, weekly priorities and inactive knowledge contracts

This change is Member 2 core functionality. It does not activate production clinical
rules, implement compact swaps, change HTTP contracts, or wire Member 1's adapters.
Base: `b96d5a46c757b40a709b87262d09eed027b86cf4` (current main). PR #19 remains
open at `c5af63328ad931df837f1f9acc331737114f8ac8`; its pipeline is checked separately
against this reasoning/schema tree. The existing six-commit integration branch is retained.

## Implemented API

`solve_weekly_plan_v2` and `verify_weekly_plan_v2` retain their existing signatures,
including `reuse_preparation=False` and `preparation_cache_entries=1`. Member 1's
explicit `reuse_preparation=True, preparation_cache_entries=1` call remains supported.
Use `WeeklyPrioritySearchStrategyV2` to supply a `WeeklyValueOrderV1`, or
`WeeklyNutrientSearchStrategyV2` to supply that declaration and a
`WeeklyNutrientContractV2`. For native nutrient results, pass the independently selected strategy as
`expected_strategy` to verification; a result's self-declared target is not authority.
Priority-only results verify their declared ordering; adapters must also compare that
declaration with the independently selected ranking release.

Seven nutrients use their native units: energy_kcal (kcal), protein_g, carbs_g,
fat_g, saturated_fat_g, sugars_g (g), and sodium_mg (mg). Source DTOs call carbohydrate
`carbohydrate_g`; adapters must explicitly map it to `carbs_g`. Values and bounds
are nonnegative decimal strings, at most three fractional digits, evaluated as
integer thousandths without rounding. DAY/WEEK lower/upper bounds support inclusive
and exclusive endpoints. No clinical threshold is supplied. Missing required values,
unknown bases or missing mass for PER_100_G remain UNKNOWN. Already validated absolute
aggregate vectors do not require invented component masses.

Priorities bind the exact request digest, source and all 21 original domains.
Higher integers run first; ties use option ID ascending. The checker reconstructs
the traversal independently and checks proof coverage in traversal order while
preserving canonical domain indices. This is first feasible search, not optimization.
Native bands are checked at complete leaves; native nutrient bound pruning is deferred.

Protocol IDs:

- `daily-nutrients.v2`, `daily-nutrient-band.v2`, `weekly-nutrient-contract.v2`,
  `weekly-nutrient-assessment.v2`, `native-decimal-3dp-no-rounding.v1`.
- `weekly-v2-value-order.v1`, `weekly-priority-search-strategy.v2`,
  `weekly-nutrient-search-strategy.v2` and their explicit synthetic policy/coverage tags.
- `computed-weekly-nutrient-solve-result.v1`: disjoint from historical weekly results.
  Do not relabel or strip its native obligations to claim old saved-plan verification.
- `reviewed-ingredient-mapping.v1`, `ingredient-mapping-review-release.v1`,
  `clinical-rule-draft.v1`.

`evaluate_weekly_nutrients` and `verify_weekly_nutrient_assessment` accept independent
request/trial/contracts. `real_integration_examples.json` supplies executable fictional
option, band and priority examples; it is not production authority.

## Inactive contracts and activation requirements

Mappings include raw/canonical identities, CONTAINS/DERIVED_FROM edges, source/version/
digest provenance, completeness and reviewer approval. Cycles and conflicting IDs are
rejected. Reviewed presence dominates unknown; verified absence needs complete,
approved evidence throughout the graph. Production release admission always returns
UNKNOWN/NOT_AUTHORIZED. There is no active release registry.

Ghee/paneer/yogurt to milk and tofu/soy sauce to soy are illustrative only. Hypertension,
type 2 diabetes and dyslipidemia declarations remain INACTIVE_NOT_AUTHORIZED with no
thresholds. See `clinical_evidence_inventory.md` for source inventory and limitations.

Member 1 must provide version-pinned canonical ingredient/derived-ingredient mappings,
source completeness, exact approved per-portion nutrient vectors and bases, catalogue
and target snapshots, and adapters binding profile, source and request identities.
Team activation requires named reviewers, review dates, authoritative evidence, exact
threshold/operator/unit/scope, applicability/exclusions, missing-data policy and a
jointly approved immutable rule release. An adapter or matching digest cannot confer
clinical approval. No production rule base is activated by this PR.

## Preliminary benchmark evidence

Two paired observations, no warmups:

| Pair | V1 seconds | V2 seconds |
|---|---:|---:|
| 1 | 327.044984 | 93.639264 |
| 2 | 404.911207 | 89.226649 |

All four returned FEASIBLE with verified witness digest
`be325fec1160634034f76f2049e4c50aaebb0e50312617af267c16aaa9a973da`.
No significance claim is made. Historical measured AI source fingerprint
`0a2fd6da2cdee07ea8395f1ea3848d2bad16e2936d372c1e36ac488905c159cb`
differs from final changes; these are not final-tree latency measurements.
The pinned Member 1 export `20261021T073631Z` contains 704 dishes / 1692 combinations;
the fixture selects 32 recipes and 21 singleton STANDARD domains. No trained Transformer
scorer was used in fixture selection. This is not unrestricted catalogue search.
Timings include mandatory result checking; additional external-source replay is outside
the paired timer. A single historical OS memory sample is not per-version memory evidence.

The original Phase 7.4 campaign remains **624/3007**: 386 feasible, 152 infeasible,
76 insufficient data and 10 verified bounded timeouts; 2383 pending. No jobs were resumed.
`savora_ai.evals.real_catalogue_benchmarks` implements only a small explicit comparison
(1..5 repeats, 0..2 warmups), not a continuation of that campaign.

## Integration and merge order

PR A is independent of PR #19 and of compact transport. It can merge before #19;
Member 1 must still wire native constraints and priorities into application orchestration.
PR B will depend on A only for its seven-nutrient DTOs; it must be reviewed separately.
Neither PR establishes an authenticated application swap workflow. Member 1 owns the
runtime resolver, authority, migrations, persistence, API/UI and end-to-end tests.

The original integration worktree and its ignored evidence remain intact. This PR
extracts files by dependency, not whole commits: notably it excludes changes to
`candidates.py`, `planned_swap.py`, `swap_proof_types.py`, envelope policy/facade,
envelope tests and the previous mixed-scope reports. Its real-data native test constructs
the weekly trial directly and has no dependency on expanded saved-plan envelopes.
