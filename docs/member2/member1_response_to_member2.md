# Member 1 → Member 2: answers to the 12 integration questions

- **From:** Diwash (Member 1, food data, meal composition, ranking)
- **To:** Venkat (Member 2, Rule Engine and CSP)
- **Date:** 19 Oct 2026, in reply to "Member 2 Technical integration response" (20 Oct draft)
- **Status:** draft for team approval; real catalogue data, no production or clinical claim
- **Review sample:** `docs/member2/member1_review_sample.json` (Q12)
- **Export:** `Data/catalogue/20261019T012206Z_*` (186 dishes, 465 meals, 2,036 configurations)

## Summary

| # | Short answer | Evidence |
|---|---|---|
| 1 | Schema documented; sample of 6 real dishes in 3 meals with original source records | contract note §2-3; review sample |
| 2 | Fat, carbohydrate, saturated fat and sugar factors verified against USDA independently of serving mass; sodium consistent but thinly evidenced | `docs/eval/dv_verification.json` |
| 3 | Yes: every portion option and every preset carries an absolute vector; the basis stays as provenance; no gram is ever inferred | portions.py; sample `contributions` |
| 4 | Yes: `null` = unknown, never zero; a per-nutrient `known` flag; a meal total is null if any component is | sample `nutrients.*.known` |
| 5 | Stable combination ID (no preset in it); preset = `portionConfigurationId`; option = `<combinationId>:<PRESET>` | sample `configurations` |
| 6 | Yes, for every preset: 7 nutrients with per-component contributions. Presets are now **checked against their label**: 50 that failed were removed | sample; ADR 0003 |
| 7 | Derived from culinary roles, from course tags plus curated overrides; every dish carries its evidence | classification.py; sample `classificationEvidence` |
| 8 | **Not ready:** ingredient names only, no canonical mapping or subingredients; allergens UNKNOWN (fail closed) | sample `ingredientMapping` |
| 9 | Implemented: energy (Mifflin-St Jeor) plus protein, carbohydrate and fat (IOM 2005 AMDR, protein RDA); sodium, saturated fat and sugar left to your KB | nutrition/targets.py |
| 10 | Ranks combination IDs (planning) or recipe IDs (craving), never portions; shortlist 2 meals x 4 presets per slot by default | recommendation/shortlist.py |
| 11 | All Member 1 modules built and tested; export available now | status table below |
| 12 | Yes: sample ready, matching your spec (one meal even shows a removed preset) | review sample |

## 1. Final output schema and a real sample

The schema is in `docs/member1_catalogue_contract.md` §2 (dish record), §2.1 (nutrition
record), §2.2 (portion options) and §3 (meals and configurations). The review sample adds
the per-nutrient evidence you asked for. It contains **6 real dishes in 3 meals**:

| Dish | Source | Basis | In meal |
|---|---|---|---|
| FC_105886 aloo dum | Food.com | PER_SERVING | 3-dish lunch (main) |
| USDA_169757 steamed white rice | USDA SR Legacy, cooked without salt | PER_100_G | 3-dish lunch (staple) |
| FC_82641 mattar paneer | Food.com | PER_SERVING | 3-dish lunch (vegetable side) |
| FC_238992 tibetan momo | Food.com | PER_SERVING | Nepali one-dish meal |
| FC_128959 chai oatmeal | Food.com | PER_SERVING | breakfast base |
| USDA_2709171 orange | USDA FNDDS | PER_100_G | breakfast fruit |

Each dish carries:
- **Identity:** `recipeId`.
- **Ingredients:** the raw ingredient list, with `ingredientMapping` = `UNRESOLVED`.
- **Nutrition:** the record (source, basis, values per basis, DV table or `fdc:` reference, quality flags) and its portion options.
- **Classification:** status and evidence.
- **Original source record:**
  - Food.com: the raw row (`nutrition` as stored, with field names) and the file SHA-256.
  - USDA: `fdc_id`, data type, description, publication date, per-100 g values and the exact `food_portion.csv` row.

All 186 dishes are in the export in the same format.

## 2. How Food.com nutrition is calculated, and the verification

**Source.**
- Dataset: Food.com Recipes and Interactions (Majumder et al., EMNLP 2019; Kaggle).
- `RAW_recipes.csv`: 294,520,189 bytes, SHA-256 `6a8136d1da9e03396a9f52d72200b3fddb8fe103f11e1496effca30ac4e0539f`.
- Its `nutrition` field is documented as `[calories (#), total fat (PDV), sugar (PDV), sodium (PDV), protein (PDV), saturated fat (PDV), carbohydrates (PDV)]`.

**Conversion:** grams = %DV / 100 x reference amount; kcal is used as stated.

**Independent verification.** Your point stands: the energy ratio says nothing about sodium
or saturated fat. So I tested each factor directly (`core/food_data/dv_verification.py`,
results in `docs/eval/dv_verification.json`):
- **Method.** For Food.com recipes made of **one food** (bacon, sweetened condensed milk,
  eggs, heavy cream, almonds, coconut, quinoa, sugar, grapes, apples), nutrient per kcal is a
  property of the food and does **not** depend on the unknown serving mass.
- **Comparison.** I compared this ratio with the USDA SR Legacy raw food under both DV tables.
  1.00 means exact agreement.
- **Exclusions.** %DV values below 5 are skipped because rounding dominates, and so are nutrients a food barely contains (for example sodium in almonds).

| Nutrient (DV) | FDA 1993 table | FDA 2016 table | Conclusion |
|---|---|---|---|
| Fat (65 g vs 78 g) | 0.96-1.04 in 6 foods | 1.15-1.25 | **1993 table confirmed** |
| Carbohydrate (300 g vs 275 g) | 0.95-0.99 in 6 foods | 0.87-0.91 | **1993 table confirmed** |
| Saturated fat (20 g in both) | 0.90-1.02 in 7 foods | same | **20 g confirmed** |
| Sodium (2,400 vs 2,300 mg) | condensed milk 1.00, bacon 0.94; eggs 1.33 | 0.96, 0.90; 1.27 | consistent with 2,400; only 3 foods / 9 recipes, eggs noisy |
| Sugar (no table) | **25 g DV: 0.97-1.05 in 6 foods (38 recipes)** | 50 g DV: about 2.0 | **Food.com used a 25 g sugar DV** |

**What this means:**
- **Fat, carbohydrate and saturated fat** are verified as factors.
- **Sodium** agrees with the 2,400 mg table where it can be tested. The two tables differ by only 4%, which is smaller than recipe-level noise, so this is consistency, not proof.
- **Sugar** can now be converted with a verified 25 g reference. I have **kept it `null`**
  until the team approves enabling it, so your "keep None" rule still holds.

**Per-serving interpretation.**
- The dataset gives nutrition per recipe serving, but not the serving count or mass.
- Evidence that it is per serving: "hard boiled eggs" (eggs + water) is 71.5 kcal, exactly one 50 g large egg at USDA's 143 kcal/100 g.
- Author-defined servings can be whole batches (an oven-bacon recipe states 3,116 kcal), which is why rows above 1,500 kcal are quarantined.

**Not available from Food.com:** original label panels or independent per-recipe sodium measurements. The dataset does not contain them.

## 3. Measurement bases

Yes. Each dish keeps its own basis as **provenance** (PER_SERVING for Food.com, PER_100_G
for USDA). Every portion option is converted to the **absolute** nutrient vector of exactly
that quantity, and every preset sums those vectors.

**Worked example** (sample, 3-dish lunch, STANDARD):

| Dish | Portion | Factor | Energy |
|---|---|---|---|
| aloo dum | 1 serving | 1.0 | x per-serving value |
| rice | 1 cup = 158 g | 1.58 | x 130 kcal/100 g |
| mattar paneer | 1 serving | 1.0 | x per-serving value |
| **Total** | | | **875.5 kcal** |

The sample lists every factor. Food.com grams stay `null` (`massKnown: false`); no mass is
ever inferred. For your `ComponentQuantity`, Food.com quantities are `serving` and USDA
quantities are `g` (`member2QuantityUnit` in the sample).

## 4. Missing values

- Every nutrient is a number or `null`. `null` means unknown and is never converted to 0.
- Each nutrient in the sample has `known: true|false`. An unknown total names the components responsible.
- Sums propagate unknowns: one unknown component makes the meal total unknown. That is why `sugarsG` is `null` in every meal that contains a Food.com dish.
- Each configuration also states `fullyKnownForRequiredNutrients`. Required means energy, fat, saturated fat, carbohydrate, protein and sodium; sugar is excluded until enabled.

## 5. Combinations and configurations

| Identity | Format | Example |
|---|---|---|
| combination | `C_<templateId>__<dishId>__...` (stable, no preset) | `C_ONE_DISH__FC_238992` |
| configuration | `portionConfigurationId` = preset, `configurationVersion` = export version | `HIGHER_PROTEIN`, `20261019T012206Z` |
| option | `<combinationId>:<PRESET>` (your opaque-ID pattern; no `#`) | `C_ONE_DISH__FC_238992:HIGHER_PROTEIN` |
| content pin | `combinationContentSha256` | in the sample |

This matches your proposal: the preset is not part of the combination ID. There are five
presets (STANDARD, HIGHER_PROTEIN, LOWER_CARB, HIGHER_ENERGY, LOWER_ENERGY). A meal keeps
1 to 5, after identical presets are merged and failing ones are removed (Q6).

## 6. Actual nutrient vectors per preset

Every configuration in the sample lists all seven nutrients (`energyKcal`, `proteinG`,
`carbohydrateG`, `fatG`, `saturatedFatG`, `sodiumMg`, `sugarsG`). Each has its unit, its
known flag, and one contribution per component (source, basis, value per basis, factor,
source reference). A test checks that every total equals the sum of its contributions,
and every contribution equals its value per basis times its factor.

**You were right that four alternatives guarantee nothing.** Building this sample from real
vectors showed that LOWER_CARB on aloo dum + rice had **more** carbohydrate (161 g) than
STANDARD (156 g): the potato curry grew more than the rice shrank. Validation now makes
each preset prove its label against STANDARD:

| Preset | Must have, compared with STANDARD |
|---|---|
| HIGHER_PROTEIN | more protein |
| LOWER_CARB | less carbohydrate |
| HIGHER_ENERGY | more energy |
| LOWER_ENERGY | less energy |

Across the catalogue, 50 presets failed and were removed, and 15 had no valid STANDARD to
compare against. The sample's 3-dish lunch therefore has STANDARD, HIGHER_PROTEIN,
HIGHER_ENERGY and LOWER_ENERGY, with no LOWER_CARB, which is a useful negative case for your tests.

## 7. Breakfast, lunch and dinner suitability

Meal types are **derived from culinary roles**, not from one tag:
- BREAKFAST_BASE and FRUIT suit breakfast.
- MAIN_DISH, STAPLE, VEGETABLE and PROTEIN_SOURCE suit lunch and dinner.

Roles come from Food.com **course** tags (main-dish, side-dishes, breakfast...).
Ingredient tags only qualify a side. Conflicting or weak evidence gives REQUIRES_REVIEW, and
those dishes are never exported. Curated overrides (29) and the 22 USDA staples are marked
CURATED. Every dish carries `classificationEvidence`, the list of rules that fired.

A meal's `mealTypes` is the intersection of its dishes' meal types and its template's.
Breakfast meals use only stand-alone breakfast dishes.

## 8. Allergens and dietary restrictions: not ready

| Item | Status today |
|---|---|
| Ingredient list | raw Food.com names (USDA: curated typical ingredients); no quantities |
| Canonical ingredient mapping | **none**: `UNRESOLVED` |
| Subingredients | **unknown** |
| Vegetarian/vegan | Food.com tags, `UNVERIFIED_METADATA` |
| Allergen status | **UNKNOWN**, so allergen rules cannot PASS (fail closed) |

**Proposal:** I map the 164 Food.com catalogue dishes' ingredients (1,902 lines, but only 606
distinct names) to your KG ingredient entities once we agree the ingredient vocabulary. Each mapping would carry
evidence and a reviewer. This is the main gap before any allergen or diet rule can resolve.

## 9. Nutrition targets

`calculate_nutrition_targets` (`core/nutrition/targets.py`, formula `targets-0.2`):

| Output | Method | Status |
|---|---|---|
| Energy target and band | Mifflin-St Jeor resting energy x activity factor x goal factor; band +/- 5% | factors PROVISIONAL |
| Meal energy shares | breakfast 20-30%, lunch 30-40%, dinner 30-40% | PROVISIONAL |
| Protein, carbohydrate, fat | IOM 2005 Dietary Reference Intakes: adult AMDR (10-35%, 45-65%, 20-35% of energy) in grams; protein at least the RDA of 0.8 g/kg | new; general reference, not clinical |
| Sodium, saturated fat, sugar | none | your sourced KB |
| BMI | informational only | |

**Schema (`NutritionTargets`):**
- Identity and provenance: `profileVersion`, `formulaVersion`, `method`, `inputHash`, `calculatedAt`, `provenance`.
- Energy: `energyKcal {min, target, max}`.
- Nutrients: `nutrientBounds [{nutrient, bounds}]`.
- Meals: `mealEnergyPolicy [{mealType, minFraction, maxFraction}]`.
- Also `bmi`.

Inputs are adults only: age 19-100, height 100-250 cm, weight 30-300 kg. Special populations
are a team decision.

## 10. Ranking and the CSP

- **Planning:** `rank_combinations` ranks combination IDs.
- **Craving:** `rank_recipes` ranks recipe IDs.
- **Neither ranks portions.** The CSP chooses a configuration.
- **Only supplied (rule-eligible) IDs are scored.**
- **Fallbacks are labelled.** Without history or a model, the result says so (`fallbackReason`); IDs the model cannot score are listed in `unscoredCandidates`.

**Per-slot candidates** (`recommendation/shortlist.py`):
- Default is your suggestion: the top 2 suitable meals x their first 4 presets, giving 8 options per slot.
- Limits are checked against your budgets: 50 per slot and 150 distinct per day.
- With lunch and dinner sharing options, a day is about 16-24 distinct options, under your 75 weekly-distinct ceiling only if the week reuses meals. We should measure this together.

**Model quality.** The Transformer + popularity hybrid ties popularity (HR@10 1.94% vs 1.91%;
69.7% vs 70.6% inside the catalogue). See `docs/reports/ranking_evaluation_report.md`.

## 11. Implementation status

| Module | Status |
|---|---|
| Food.com normalisation, quarantine, classification | done, tested |
| USDA staples (22, exact identity) and portions | done, tested |
| Popularity (training cutoff), stratified selection | done, tested |
| Meal composition, presets, nutrition validation incl. preset intent | done, tested |
| Coverage (8 scenarios; 7 sufficient, Nepali breakfast is a data gap) | done |
| Nutrition targets: energy + macros | done, tested |
| Transformer, baselines, evaluation (3 seeds, bootstrap, ablations) | done, tested |
| Ranking API, per-slot shortlist | done, tested |
| Explanation builder (consumes your traces, does not rewrite rule status) | done, tested |
| %DV verification | done; sugar enable pending approval |
| Review sample for Member 2 | **ready now** |
| Canonical ingredient mapping, allergen evidence | **not started**: needs the agreed vocabulary |
| Real seven-nutrient measurement in your CSP | yours (ADAPTER_REQUIRED) |

**Testing:** 300+ Member 1 tests and 94% line coverage of Member 1 modules. The whole repository passes, including your suites (`docs/reports/test_report.md`).

## 12. Joint test

Yes. The sample at `docs/member2/member1_review_sample.json` matches your request:

| Your request | In the sample |
|---|---|
| 2-3 combinations | 3 |
| Four presets each | 4 each; the 3-dish meal shows the preset-intent removal |
| A USDA-based component | rice (SR Legacy) and orange (FNDDS) |
| A missing nutrient | sugar (`null`, `known: false`, reason given) |
| Expected per-slot candidates | `slotShortlists` for breakfast, lunch and dinner |
| Original source records | Food.com rows with file SHA-256; USDA records |
| Field status | EXISTING / ADAPTER_REQUIRED / PROPOSED (`fieldStatus`) |

Regenerate it with:
`uv run python -m savora_ai.core.meal_composition.review_export` (optionally
`--combination <id>`).

The sample is labelled `REVIEW_SAMPLE` and never `SYNTHETIC`. Separately, our test
`test_member2_adapter_integration.py` already runs real export meals through your
`solve_daily_plan` under a SYNTHETIC label, because that is all your contracts accept today.

## Decisions I need from you or the team

1. Approve the 7 nutrient keys and units (identical to your table), precision (3 decimals
   in the sample) and the integer rounding you need for measurements.
2. Approve enabling Food.com sugar with the verified 25 g reference.
3. Decide the source-admission policy per rule (you proposed rule-specific, not universal tiers; agreed).
4. Agree the ingredient vocabulary so I can map the catalogue ingredients (Q8).
5. Measure solver time on the shortlist sizes above with the sample.
