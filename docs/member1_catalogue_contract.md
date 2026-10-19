# Member 1 catalogue export: contract note for Members 2 and 3

- **Status:** Proposed by Member 1, 18 Oct 2026. Not yet jointly approved.
- **Audience:** Venkat (Member 2, Rule Engine and CSP), Aryaman (Member 3, persistence and
  orchestration).
- **Relates to:** ADR 0001 to 0003, ARCHITECTURE.md sections 3, 6, 8 and 9.

This note says what the export files contain, what every field means, which units are
used and what `null` means. It also proposes how the fields map onto Member 2's
contracts in `savora_ai.schemas`. The mapping is a proposal; nothing in Member 2's code
was changed.

## 1. Files

One build writes three files with the same version (UTC build time, `YYYYMMDDTHHMMSSZ`,
which sorts chronologically as text):

| File | Content | Size (current) |
|---|---|---|
| `Data/catalogue/<v>_catalogue.json` | 186 dishes: 164 Food.com recipes and 22 USDA staples, with portions and nutrition | 0.7 MB |
| `Data/catalogue/<v>_combinations.json` | 465 validated meals of 1 to 3 dishes, 2,036 portion configurations | 2.5 MB |
| `Data/catalogue/<v>_build_report.json` | counts, strata, composition, validation and coverage | 15 KB |

`<v>_combinations.json` carries `catalogueContentSha256`, the SHA-256 of the canonical
JSON of the catalogue's `recipes` array. A consumer can check that a combinations file
belongs to the catalogue it loaded.

Rebuild: `uv run python -m savora_ai.core.food_data.build_catalogue --source
Data/Food.com/RAW_recipes.csv`. Check that a committed export is current: add `--check`.
Builds are deterministic for the same inputs and seed.

## 2. Dish record (`recipes[]` in the catalogue)

| Field | Type | Meaning |
|---|---|---|
| `recipeId` | string | `FC_<food.com id>` or `USDA_<fdc id>`; stable across builds |
| `name` | string | display name |
| `ingredients` | string[] | Food.com: the raw ingredient list. USDA: curated typical ingredients of the plain food |
| `cuisines` | string[] | from exact tags or curation; **empty = cuisine-neutral** (plain vegetables, fruit, egg) |
| `dietTags` | string[] | `vegetarian`, `vegan`: **unverified metadata**, not a diet fact. The Rule Engine must decide from ingredients |
| `roles` | `CulinaryRole[]` | several allowed |
| `dishClass` | `COMPLETE_MEAL` \| `REQUIRES_ACCOMPANIMENT` \| `COMPONENT` | can it stand alone |
| `mealTypes` | `MealType[]` | derived from roles |
| `classificationStatus` | `AUTO` \| `CURATED` | only settled dishes are exported (`REQUIRES_REVIEW` never is) |
| `classificationEvidence` | string[] | every rule that fired, and the curation note |
| `nutrition` | object | see 2.1 |
| `servingMassG`, `servingMassSource` | number \| null | null = **unknown**; set only with a recorded source |
| `trainingInteractions` | int \| null | Food.com interactions before the popularity cutoff; null for USDA staples |
| `portions` | object[] | see 2.2 |
| `provenance` | string[] | source file, conversion, portion origin |

### 2.1 `nutrition`

| Field | Meaning |
|---|---|
| `source` | `FOODCOM_DERIVED` (kcal + %DV converted with a named table), `USDA_FNDDS`, `USDA_SR_LEGACY`, `USDA_FOUNDATION`, `CURATED` |
| `basis` | `PER_SERVING` (Food.com, one recipe serving, mass unknown) or `PER_100_G` (USDA) |
| `values` | `energyKcal`, `fatG`, `saturatedFatG`, `carbohydrateG`, `proteinG`, `sodiumMg`, `sugarsG` |
| `sourceReference` | DV table name, or `fdc:<id> <description> (<date>)` |
| `qualityFlags` | problems found in the source values |

**`null` means unknown and is never zero.** Food.com `sugarsG` is always null (no
verified DV reference). Food.com sodium and saturated fat use an **assumed** DV table
(ADR 0001 D1); verify before a sodium rule relies on them.

### 2.2 `portions[]`

| Field | Meaning |
|---|---|
| `portionId` | `<recipeId>:<quantity>x<unit>`, e.g. `USDA_2707713:2xPIECE` |
| `quantity`, `unit` | Food.com: 0.5 to 1.5 `SERVING`. USDA: household unit (`PIECE`, `CUP`, `SLICE`) |
| `grams` | real mass for USDA portions (from `food_portion.csv`); **null for Food.com servings** |
| `isStandard` | exactly one per dish |
| `nutrients` | the **absolute** nutrients of exactly this quantity (rounded to 3 decimals) |

The CSP never needs a dish's mass: it adds `nutrients` vectors.

## 3. Meal combinations (`combinations[]`)

| Field | Meaning |
|---|---|
| `combinationId` | `C_<templateId>__<dishId>__<dishId>`, dishes in slot order |
| `templateId` | `ONE_DISH`, `MAIN_STAPLE`, `MAIN_STAPLE_VEGETABLE`, `BREAKFAST`, `BREAKFAST_FRUIT`, `BREAKFAST_PROTEIN` |
| `mealTypes` | meals every component suits |
| `cuisines` | the anchor (first) dish's cuisines |
| `components[]` | `{slot, dishId, role}` |
| `configurations[]` | 1 to 5 curated presets, see below |
| `evidence` | template rationale, pairing, side choice |

Each configuration:

| Field | Meaning |
|---|---|
| `configurationId` | `<combinationId>#<PRESET>` |
| `preset` | `STANDARD`, `HIGHER_PROTEIN`, `LOWER_CARB`, `HIGHER_ENERGY`, `LOWER_ENERGY` |
| `portions[]` | `{dishId, portionId, quantity, unit, grams}` per component, in component order |
| `nutrition.totals` | sum per nutrient; **null if any component's value is null** |
| `nutrition.sourceTier` | the weakest source among the components |
| `nutrition.fullyKnown` | every required nutrient known for every component |
| `nutrition.unknownNutrients` | required nutrients that are unknown |

Required nutrients: energy, fat, saturated fat, carbohydrate, protein, sodium (not sugar).
Every exported configuration has known, recomputed energy within 150 to 2,000 kcal.

**Every current meal has `sourceTier = FOODCOM_DERIVED`**, because every meal has a
Food.com anchor dish. If derived nutrition does not count as known for hard clinical
rules, no current meal can pass one. This is question 2 below.

## 4. Proposed mapping onto Member 2's contracts

| Member 2 field (`savora_ai.schemas`) | From the export |
|---|---|
| `RecipeSnapshotReference.recipe_id` | `recipeId` |
| `RecipeSnapshotReference.catalogue_version`, `recipe_version` | the build version (one content version per build, for now) |
| `RecipeSnapshotReference.content_digest` | SHA-256 of the dish's canonical JSON (to add on export) |
| `CombinationComponent.component_id` | `<combinationId>/<slot>` |
| `CombinationComponent.role_references` | `role` → a `CULINARY_ROLE_REFERENCE` entity per `CulinaryRole` (IDs to agree) |
| `ComponentQuantity.amount`, `unit` | Food.com: `quantity` with `QuantityUnit.SERVING`; USDA: `grams` with `QuantityUnit.G` |
| `VersionedFact.measurement_basis` | `nutrition.basis`; the tokens `PER_SERVING`, `PER_100_G` are identical |
| `MealOptionReference.portion_configuration_id` | `configurationId`, with `PortionState.FIXED` |
| `FixedMealMeasurement.value` | a `nutrition.totals` value; needs an **integer rounding policy** |
| `MealSlotSuitability.slots` | `mealTypes`; tokens `BREAKFAST`, `LUNCH`, `DINNER` are identical |

Blocking fact: Member 2's candidate contracts currently accept **SYNTHETIC evidence only**
(`_validate_provenance`). The real catalogue cannot be passed into them until the team
approves a production evidence path. Until then, Member 2 can test against this export
through an adapter that labels it SYNTHETIC in tests.

## 4a. Scenario A: implemented with assumed answers

So the work is not blocked, `core/meal_composition/member2_adapter.py` implements ONE
assumed answer to each question below, all in the `SCENARIO_A` block. If Member 2
decides differently, only that block changes. Assumptions:

| # | Assumed answer |
|---|---|
| Q1 | Food.com quantities use `QuantityUnit.SERVING`; USDA quantities use grams |
| Q2 | Food.com-derived nutrition counts as known (`complete=True`); `null` stays incomplete |
| Q3 | Meal totals are integers rounded half-up |
| vocabulary | Real facts are published under Member 2's admitted synthetic names: classification settled = `synthetic_flag`; sodium per serving = `synthetic_serving_quantity`; sodium per 100 g = `synthetic_quantity`; template-built meal = `synthetic_combination_roles_compatible` and `_composition_complete` |
| measurement | The one daily meal measurement (mg only) carries the meal's **sodium** total, summed into `synthetic_day_quantity_total` |
| evidence | Labelled SYNTHETIC (the only environment accepted); not for production |
| ingredients | Listed but not mapped to canonical ingredients: `UNRESOLVED_MAPPING`, so ingredient rules stay UNKNOWN |

**Verified end to end** (`tests/test_member2_adapter_integration.py`). Real dishes and
meals from the committed export pass Member 2's strict contracts, recipe filter and
`solve_daily_plan`. With a day sodium cap of 10,000 mg the day is FEASIBLE (342 + 649 +
649 mg). At 1,500 mg the solver backtracks (6 nodes) and swaps dinner for a 218 mg meal.
At 1 mg it is INFEASIBLE.

Gaps found while integrating, for Member 2:

- The daily measurement only accepts mg, so **meal energy (kcal) cannot be constrained**
  yet. Calorie targets need a second measurement attribute or a kcal unit.
- The daily solver allowed the **same meal at lunch and dinner**; a within-day repetition
  rule is needed.
- Only synthetic attribute names are admitted; real names (sodium, energy, diet,
  allergens) need approved policies.

## 5. Questions needing an answer

1. **Venkat:** accept `PER_SERVING` quantities in `serving` units next to grams (the
   contract allows `QuantityUnit.SERVING`; please confirm the solver uses it).
2. **Venkat:** does `FOODCOM_DERIVED` nutrition count as known for hard clinical rules?
   May a `PARTIAL` meal pass one?
3. **Venkat:** integer rounding policy for `FixedMealMeasurement` (half-up to 1 kcal,
   1 mg, 0.1 g scaled?) and the trust order of `SOURCE_TRUST`.
4. **Venkat:** solver time on 465 meals and about 4.4 configurations each. That sets
   `CompositionLimits` and the quota of 10 per stratum.
5. **Team:** under a STRICT cuisine policy, may breakfast use cuisine-neutral dishes?
   No Nepali breakfast exists in Food.com.
6. **Aryaman:** storage of combinations and configurations (`meal_combinations`,
   `meal_combination_components`); the export IDs are stable and can be primary keys.
7. **Team:** `curatedBy: "ai-review:claude"` entries were curated by AI judgement at the
   project lead's request; a person should confirm them before production use.
