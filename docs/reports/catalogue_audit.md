# Catalogue audit for planning (21 October 2026)

Catalogue `20261019T012206Z`: 186 dishes (164 Food.com, 22 USDA staples, vegetables and
fruit) and 465 meal combinations. The audit runs the integration pipelines' own meal
selection (`core/pipelines/planning.py::_ranked_meals`) over the 8 proxy profiles of the
coverage report.

Method:
- diet uses the unverified Food.com tags; a missing tag excludes the dish
- exclusions are whole-word ingredient matches
- a week needs 4 distinct breakfast anchor dishes and 7 distinct main anchors, because a
  dish may repeat at most twice

This audit is not the Rule Engine and makes no clinical statement.

## 1. Weekly plan coverage per profile

| Profile | Breakfast anchors (need 4) | Main anchors (need 7) | Week possible |
|---|---|---|---|
| mixed, no restriction | 49 | 110 | yes |
| Indian vegetarian, strict | 7 | 11 | yes |
| **Nepali, strict** | **0** | 15 | **no**: no Nepali breakfast in the catalogue |
| Indian or Nepali, explicit beef exclusion | 10 | 28 | yes |
| Thai, strict, peanut excluded | 6 | 8 | yes (1 main to spare) |
| Chinese, strict, pork excluded | 9 | 13 | yes |
| Mexican vegetarian, strict | 5 | 8 | yes (1 to spare in each) |
| vegan, mixed | 8 | 22 | yes |

Breakfast anchors by cuisine: American 11, Chinese 11, Italian 10, Mexican 10, Indian
10, Thai 10, and 1 each for Spanish, Japanese and Middle Eastern. **Nepali has 0** (it
has 15 main anchors).

## 2. Breakfast anchors that are lunch or dinner dishes

Breakfast roles come from Food.com tags (`AUTO` classification). These 14 anchors are
lunch or dinner dishes and should lose `BREAKFAST_BASE` through a classification override:

| Recipe | Name | Roles today |
|---|---|---|
| FC_104630 | balsamic tomato basil pasta | STAPLE, MAIN_DISH, BREAKFAST_BASE |
| FC_119772 | chinese gingered rice | STAPLE, BREAKFAST_BASE |
| FC_125496 | veggie pasta shells oamc | MAIN_DISH, BREAKFAST_BASE |
| FC_133760 | hainanese chicken rice | MAIN_DISH, BREAKFAST_BASE |
| FC_137891 | rice noodles with chicken | MAIN_DISH, BREAKFAST_BASE |
| FC_181005 | thai curry burger with grilled onions and curry dressing | MAIN_DISH, BREAKFAST_BASE |
| FC_195593 | chickpeas and rice | STAPLE, MAIN_DISH, BREAKFAST_BASE |
| FC_208095 | golden basmati rice | STAPLE, BREAKFAST_BASE |
| FC_225320 | basic oriental fried rice | STAPLE, MAIN_DISH, BREAKFAST_BASE |
| FC_56864 | chicken curry soup with coconut and lime | BREAKFAST_BASE |
| FC_81138 | taco bell chalupa copycat | STAPLE, MAIN_DISH, BREAKFAST_BASE |
| FC_82971 | coconut basmati rice | STAPLE, BREAKFAST_BASE |
| FC_84231 | singapore rice noodles | MAIN_DISH, BREAKFAST_BASE |
| FC_88719 | mulligatawny soup with lentils | BREAKFAST_BASE |

These are kept as genuine breakfasts: FC_27028 masala dosa and FC_472074 Burmese
breakfast fried rice.

Effect of removing them, measured as breakfast anchors before → after (4 needed):

| Profile | Before | After |
|---|---|---|
| mixed, no restriction | 49 | 35 |
| Indian vegetarian, strict | 7 | 4 (no spare) |
| Indian or Nepali, beef excluded | 10 | 7 |
| **Thai, strict, peanut excluded** | 6 | **2: week no longer possible** |
| Chinese, strict, pork excluded | 9 | 6 |
| Mexican vegetarian, strict | 5 | 5 |
| vegan, mixed | 8 | 4 (no spare) |

## 3. Nutrition and portion completeness

- **Sugars are unknown for all 164 Food.com dishes.** Explanations name sugar as unknown,
  and any rule that needs sugar would evaluate UNKNOWN (fail closed) until a source is
  added, for example USDA ingredient-level estimation.
- **Serving mass is unknown for all 164 Food.com dishes**, so their portions stay in
  servings and gram-based comparisons cannot run on them.
- Every combination has a validated STANDARD configuration with a known sodium total, so
  no meal is lost to the CSP's sodium measurement.

## 4. Fix plan (Member 1; needs dish choices before the export is rebuilt)

1. Add at least 4 Nepali breakfast dishes (from Food.com where they exist, otherwise as
   curated dishes with USDA-based nutrition), each with an override and portions.
2. Add at least 3 Thai breakfasts without peanut, and 2–3 Indian-vegetarian and vegan
   breakfasts. Do this **in the same rebuild** as step 3, otherwise Thai plans break.
3. Apply the 14 overrides in section 2.
4. Rebuild the export (new catalogue version), re-run this audit and the coverage
   report, and update tests that pin the catalogue version.
