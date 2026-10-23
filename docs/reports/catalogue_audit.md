# Catalogue audit for planning (21 October 2026)

Catalogue `20261021T073631Z`: 704 dishes (679 Food.com, 25 USDA staples, vegetables and
fruit), 1,692 meal combinations, 19 target cuisines. It replaces `20261020T230903Z`
(697 dishes, 1,673 meals), which replaced `20261019T012206Z` (186 dishes, 465 meals,
10 cuisines). Section 6 lists what changed in this rebuild.

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
| mixed, no restriction | 185 | 451 | yes |
| Indian vegetarian, strict | 11 | 19 | yes |
| Nepali, strict | 4 | 15 | yes (no spare breakfast; solved FEASIBLE in 135 s) |
| Indian or Nepali, explicit beef exclusion | 17 | 38 | yes |
| Thai, strict, peanut excluded | 9 | 10 | yes |
| Chinese, strict, pork excluded | 12 | 22 | yes |
| Mexican vegetarian, strict | 8 | 12 | yes |
| vegan, mixed | 18 | 87 | yes |

Counts are for catalogue `20261021T073631Z` (section 6). Before it, strict Nepali had 0
breakfasts; the 186-dish catalogue gave Thai 6 / 8, Indian vegetarian 7 / 11, vegan 8 / 22.

### Anchors by cuisine

| Cuisine | Breakfast | Main |
|---|---|---|
| American | 18 | 33 |
| Indian | 17 | 29 |
| Chinese, Thai | 16 | 25–26 |
| Italian, Middle Eastern, Caribbean, Greek, French, Mexican, Spanish, Moroccan | 15 each | 24–29 |
| Japanese | 13 | 29 |
| Malaysian | 9 | 26 |
| Vietnamese | 7 | 27 |
| Korean | 6 | 29 |
| Filipino, Indonesian | 5 | 27 |
| Nepali | **4** (no spare) | 15 |

Every target cuisine can now fill a strict single-cuisine week. Nepali has exactly the 4
breakfasts a week needs, so a Nepali-strict profile that also excludes one of them (for
example eggs) cannot plan a week; that profile gets INSUFFICIENT_DATA, not a wrong plan.

## 3. Breakfast anchors still worth a look

The guard leaves these breakfast anchors, which need a human decision. Each could be
kept or removed with an override:

| Recipe | Name | Note |
|---|---|---|
| FC_109823 | drstevers filipino stir fry | **resolved**: now a main only (section 6) |
| FC_27743 | easy veggie burrito for one vegan | breakfast burritos are common; keep |
| FC_335900 | spicy minced pork rice porridge | porridge; keep |

## 4. Nutrition and portion completeness

- Sugar is known for 692 of 697 dishes. The 5 unknown ones fail closed in any sugar
  rule.
- **Serving mass is unknown for all 675 Food.com dishes**, so their portions stay in
  servings and gram-based comparisons cannot run on them (unchanged).
- Every combination has a validated STANDARD configuration with a known sodium total.

## 5. Remaining work (Member 1)

None of the three items from the previous audit remains (section 6). Still open, and not
blocking: more Nepali breakfasts for a spare, and a person to confirm the
`ai-review:claude` curation.

## 6. Rebuild `20261021T073631Z` (21 October 2026)

| Change | Entries | Why |
|---|---|---|
| New USDA staples (breakfast bases, same-food FNDDS records, ADR 0003 D1) | puri (2707714), paratha (2707715): Indian, Nepali. Rice congee with egg (2708984): Chinese, Korean, Vietnamese, Filipino, Indonesian, Malaysian, Thai | Nepali had no breakfast; congee is the everyday breakfast porridge of these cuisines |
| Food.com overrides, breakfast base | FC_478796 alu paratha and FC_482891 indian omelet (+ Nepali), FC_459783 egg rice (Korean), FC_99028 banana pancakes (Indonesian) | tagged breakfast and common in those cuisines |
| Food.com override, breakfast and main | FC_478798 nasi goreng | eaten at breakfast as often as later |
| Food.com override, main only | FC_109823 drstevers filipino stir fry | a tofu stir-fry with rice, not a breakfast base |

Rejected: `egg bara` (5,659 kcal per serving, broken data), `churu` (a westernised blue
cheese soup), `egg jjim` (202% DV sodium per serving). The reasons are recorded in
`Data/curated/classification_overrides.json` and `Data/curated/usda_staples.json`.
