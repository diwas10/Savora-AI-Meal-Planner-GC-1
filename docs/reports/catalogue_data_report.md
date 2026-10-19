# Catalogue data report (Member 1)

- **Export:** `Data/catalogue/20261018T192730Z_*` (catalogue, combinations, build report)
- **Rebuild:** `uv run python -m savora_ai.core.food_data.build_catalogue --source
  Data/Food.com/RAW_recipes.csv`; `--check` confirms the committed export is current
  (it passed on this export).
- **Inputs:** Food.com `RAW_recipes.csv` (231,637 rows, SHA-256 in the export),
  `RAW_interactions.csv` (popularity, before 2012-01-01 only), curated files in
  `Data/curated/` (classification overrides, 22 USDA staples and their extract, meal
  templates, pairings).

All numbers below come from that build report; nothing is estimated.

## 1. The funnel: 231,637 raw rows to 475 meals

| Stage | Count | What happens |
|---|---|---|
| Raw Food.com rows | 231,637 | |
| Quarantined (data defect, kept for review) | 17,941 | 11,457 out of range, 6,484 energy-inconsistent, 1 malformed |
| Accepted | 213,696 | |
| Not a planning dish (desserts, drinks, sauces) | 55,213 | AUTO, no role |
| Requires review (conflicting or weak tags) | 52,140 | written to the review queue, never selected |
| **Plannable** | **106,343** | AUTO 106,318 + CURATED 25 |
| Selected by stratified selection | 164 | 7 cuisines x 4 slot kinds |
| + curated USDA staples | 22 | rice, roti, naan, noodles, fruit, egg... |
| **Catalogue dishes** | **186** | |
| Meals composed | 479 | 6 templates, bounded |
| Meals rejected by nutrition validation | 4 | every preset outside 150-2,000 kcal |
| **Exported meals** | **475** | 2,101 portion configurations |

Every row is accounted for: accepted + quarantined = raw; plannable + review + not
planning = accepted (tests assert both).

## 2. Data quality gates

| Gate | Rule | Result |
|---|---|---|
| Nutrition parse | 7 finite non-negative numbers | 0 failures |
| Range | 10 to 1,500 kcal per serving; no %DV above 300 | 11,457 quarantined |
| Energy consistency | Atwater/stated within 0.75-1.25, or a gap within 10 kcal (rounding) | 6,484 quarantined |
| Meal plausibility | a meal dish has 50 kcal or more; a side has 700 kcal or less | sent to review |
| USDA identity | `fdcId` description equals the curated expectation | 22 of 22 matched |
| USDA portion | pinned `food_portion.csv` row belongs to the food | 22 of 22 matched |
| Meal energy | recomputed from base records within 1 kcal; within 150 to 2,000 kcal | 59 configurations dropped |
| Completeness | energy, fat, saturated fat, carbohydrate, protein, sodium known | 2,101 of 2,101 FULLY_KNOWN |

## 3. Plannable dishes by role and class (106,343)

| Role | Dishes | | Dish class | Dishes |
|---|---|---|---|---|
| MAIN_DISH | 65,578 | | COMPLETE_MEAL | 44,867 |
| VEGETABLE | 17,345 | | REQUIRES_ACCOMPANIMENT | 34,214 |
| BREAKFAST_BASE | 16,804 | | COMPONENT | 27,262 |
| STAPLE | 15,888 | | | |

A dish can hold several roles, so role counts add up to more than 106,343.

## 4. The catalogue (186 dishes)

| Cuisine | Dishes | | Meal type | Dishes | | Nutrition source | Dishes |
|---|---|---|---|---|---|---|---|
| Indian | 37 | | BREAKFAST | 59 | | FOODCOM_DERIVED | 164 |
| Mexican | 34 | | LUNCH | 167 | | USDA_FNDDS | 13 |
| American | 33 | | DINNER | 167 | | USDA_SR_LEGACY | 9 |
| Chinese | 31 | | | | | | |
| Thai | 31 | | | | | | |
| Italian | 29 | | | | | | |
| Nepali | 18 | | | | | | |
| cuisine-neutral | 11 | | | | | | |

104 dishes (56%) carry a vegetarian tag. Some dishes have two cuisines (for example
Indian and Nepali), and a few carry a non-target cuisine as a second label (Spanish,
Japanese, Middle Eastern).

### Strata (quota 10, vegetable side 4)

Every stratum of Thai, Chinese, Indian, Mexican, Italian and American is full. Only
Nepali is short, and that is a data limit, not a quota choice:

| Nepali stratum | Selected / quota | Eligible in data |
|---|---|---|
| breakfast base | 0 / 10 | 0 |
| complete main | 7 / 10 | 7 |
| main needing an accompaniment | 8 / 10 | 8 |
| vegetable side | 0 / 4 | 0 (cuisine-neutral USDA vegetables fill this role) |

## 5. Meals (475 exported)

| Template | Meals | | Meal type | Meals |
|---|---|---|---|---|
| MAIN_STAPLE | 122 | | BREAKFAST | 179 |
| MAIN_STAPLE_VEGETABLE | 122 | | LUNCH | 300 |
| BREAKFAST_FRUIT | 98 | | DINNER | 300 |
| ONE_DISH | 56 | | | |
| BREAKFAST | 49 | | | |
| BREAKFAST_PROTEIN | 32 | | | |

Per cuisine: American 90, Chinese 89, Indian 88, Thai 88, Italian 87, Mexican 85,
Nepali 39. 20 breakfast add-ons were skipped because the base already contained them
(whole-word match). Portion configurations: 2,101, about 4.4 per meal.

**Source tier:** all 2,101 configurations are `FOODCOM_DERIVED`, because every meal has a
Food.com anchor dish. Whether that tier counts as known for hard clinical rules is open
question Q2 for Member 2.

## 6. Scenario coverage (proxy, not the Rule Engine)

A scenario is sufficient with 4 or more distinct breakfast anchors and 7 or more distinct
lunch/dinner anchors (7 and 14 slots, at most 2 repeats a week).

| Scenario | Breakfast | Lunch/dinner | Enough for a week |
|---|---|---|---|
| mixed, no restriction | 49 | 117 | yes |
| Indian vegetarian, strict | 7 | 13 | yes |
| Nepali, strict | **0** | 15 | **no** |
| Indian or Nepali, explicit beef exclusion | 10 | 30 | yes |
| Thai, strict, peanut excluded | 6 | 8 | yes |
| Chinese, strict, pork excluded | 9 | 17 | yes |
| Mexican vegetarian, strict | 5 | 10 | yes |
| vegan, mixed | 8 | 25 | yes |

**7 of 8 sufficient.** The previous export reached 6 of 8; fixing the breakfast stratum
rule (code review) added 30 breakfast meals and made the Thai peanut-free scenario
sufficient. Nepali breakfast stays empty: Food.com has no Nepali breakfast dishes.
Whether a STRICT cuisine user may receive cuisine-neutral breakfasts is team question Q5.

## 7. Known limitations

- Food.com nutrition is derived from %DV with an assumed sodium and saturated-fat table;
  sugar is always unknown.
- Food.com serving sizes vary widely (one meal configuration reaches about 1,600 kcal at
  standard portions); the 2,000 kcal ceiling removes only the extreme ones.
- Ingredients are listed but not mapped to canonical ingredient entities, so allergen
  rules cannot resolve to PASS yet (they stay UNKNOWN, which fails closed).
- Diet tags are unverified Food.com metadata.
- All curation is marked `curatedBy: ai-review:claude` and needs human confirmation.
