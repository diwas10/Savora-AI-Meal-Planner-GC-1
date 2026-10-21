# Catalogue audit for planning (21 October 2026)

Catalogue `20261020T230903Z`: 697 dishes (675 Food.com, 22 USDA staples, vegetables and
fruit), 1,673 meal combinations, 19 target cuisines. It replaces `20261019T012206Z`
(186 dishes, 465 meals, 10 cuisines).

The audit runs the integration pipelines' own meal selection
(`core/pipelines/planning.py::_ranked_meals`) over the 8 proxy profiles of the coverage
report.

Method:
- diet uses the unverified Food.com tags; a missing tag excludes the dish
- exclusions are whole-word ingredient matches
- a week needs 4 distinct breakfast anchor dishes and 7 distinct main anchors, because a
  dish may repeat at most twice

This audit is not the Rule Engine and makes no clinical statement.

## 1. What changed in the rebuild

- **Cuisines:** 19 targets (Malaysian, Indonesian, Filipino, Korean, Vietnamese, Japanese,
  Moroccan, Spanish, Thai, Caribbean, Chinese, Middle Eastern, French, Greek, Indian,
  Mexican, Italian, American and Nepali), with selection quotas of 15 breakfasts, 15
  mains, 15 sides and 5 snacks per cuisine. Malaysian, Indonesian, Filipino, Moroccan
  and Caribbean are catalogue cuisine tags taken from Food.com; the EDA taxonomy is
  unchanged.
- **Breakfast guard:** a Food.com breakfast tag no longer makes a curry, soup, pasta,
  noodle, burger, stew, biryani, kebab, enchilada (and so on) a breakfast base. Plain
  rice dishes are also excluded unless they are porridge, congee, pudding or cereal, or
  the name says breakfast. All 14 anchors flagged in the previous audit are gone.
- **Thai breakfasts:** 3 curated overrides (rice soups and porridge).
  `Data/curated/classification_overrides.json` explains why the other candidate was
  rejected.
- **Sugar:** the Food.com sugar %DV now converts with a verified 25 g reference (ADR
  0001 D2, revised). Sugar is known for every dish except 5. For those 5 the converted
  value exceeded the carbohydrate value, so it stays unknown.
- **Pairings:** 12 new cuisine pairings (rice and rice noodles for South-East Asian
  cuisines, bread and potato for European ones, and so on).

## 2. Weekly plan coverage per profile

| Profile | Breakfast anchors (need 4) | Main anchors (need 7) | Week possible |
|---|---|---|---|
| mixed, no restriction | 179 | 451 | yes |
| Indian vegetarian, strict | 8 | 19 | yes |
| **Nepali, strict** | **0** | 15 | **no**: no Nepali breakfast (deferred) |
| Indian or Nepali, explicit beef exclusion | 15 | 38 | yes |
| Thai, strict, peanut excluded | 8 | 10 | yes |
| Chinese, strict, pork excluded | 11 | 22 | yes |
| Mexican vegetarian, strict | 8 | 12 | yes |
| vegan, mixed | 18 | 88 | yes |

Previous catalogue, same profiles: Thai 6 / 8, Indian vegetarian 7 / 11, vegan 8 / 22.
The Thai week would have broken (2 breakfasts) once the bad anchors were removed.

### Anchors by cuisine

| Cuisine | Breakfast | Main |
|---|---|---|
| American | 18 | 34 |
| Thai, Italian, Middle Eastern, Caribbean, Greek, French, Mexican, Spanish, Indian, Chinese, Moroccan | 15 each | 27–30 |
| Japanese | 13 | 30 |
| Malaysian | 8 | 30 |
| Vietnamese | 6 | 29 |
| Filipino | 5 | 28 |
| Korean | **4** (no spare) | 29 |
| Indonesian | **2** | 29 |
| Nepali | **0** | 15 |

A **strict single-cuisine** week is not possible for Indonesian or Nepali, and has no
spare for Korean, because Food.com has few breakfasts tagged with these cuisines. Mixed
or preferred-cuisine profiles are unaffected.

## 3. Breakfast anchors still worth a look

The guard leaves these breakfast anchors, which need a human decision. Each could be
kept or removed with an override:

| Recipe | Name | Note |
|---|---|---|
| FC_109823 | drstevers filipino stir fry | likely a main; Food.com tags it breakfast |
| FC_27743 | easy veggie burrito for one vegan | breakfast burritos are common; keep |
| FC_335900 | spicy minced pork rice porridge | porridge; keep |

## 4. Nutrition and portion completeness

- Sugar is known for 692 of 697 dishes. The 5 unknown ones fail closed in any sugar
  rule.
- **Serving mass is unknown for all 675 Food.com dishes**, so their portions stay in
  servings and gram-based comparisons cannot run on them (unchanged).
- Every combination has a validated STANDARD configuration with a known sodium total.

## 5. Remaining work (Member 1)

1. Nepali breakfasts: 4 or more, as curated dishes with USDA-based nutrition, or from
   Food.com, which has 53 recipes tagged `nepalese`. This item was deferred by the team
   on 21 October 2026.
2. Indonesian and Korean breakfasts: 2 or more each, the same way.
3. Decide FC_109823.
