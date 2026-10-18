# ADR 0001: Catalogue v0 and nutrition basis

- **Status:** Proposed by Member 1 for team approval. Not yet jointly approved.
- **Date:** 2026-10-18 (revised 2026-10-18 after design review)
- **Owner:** Member 1 (Food.com/USDA normalization, portion definitions)
- **Relates to:** ARCHITECTURE.md sections 3, 5, 8, 15; Food.com EDA (`eda/food.com_eda.md`);
  ADR 0002 (composition), ADR 0003 (nutrition sources)

## Context

The CSP needs nutrition per reference quantity and discrete portions (ARCHITECTURE.md
section 8). Food.com provides, per recipe, `[kcal, total fat %DV, sugar %DV, sodium %DV,
protein %DV, saturated fat %DV, carbohydrates %DV]`. These are percentages of a daily
reference, not grams, and the dataset has **no serving mass**. A per-100 g value therefore
cannot be derived from Food.com alone, and the architecture forbids treating missing
nutrition as zero or inventing facts.

The raw data also has extreme values (maximum kcal 434,360; sugar %DV 362,729) and no
`dinner` or `nepali` tag.

## Decisions

### D1. %DV is converted with the FDA 1993 labelling table

100 %DV = fat 65 g, saturated fat 20 g, carbohydrate 300 g, protein 50 g, sodium 2,400 mg.

**Evidence.** On 196,627 recipes with plausible values, the energy implied by the converted
macros (`9*fat + 4*carbohydrate + 4*protein`) was compared with the stated kcal. For each
recipe the ratio `implied / stated` is computed; the table reports the median and the
interquartile range of those ratios:

| DV table | Median implied/stated | Interquartile range | Within +/-25% |
|---|---|---|---|
| FDA 1993 (fat 65, carbohydrate 300, protein 50) | 0.982 | 0.959 to 1.003 | 98.2% |
| FDA 2016 (fat 78, carbohydrate 275, protein 50) | 1.033 | 0.983 to 1.079 | 98.2% |

The 1993 table is closer to 1.0 and tighter, consistent with Food.com's 2008 to 2018 data.

**Limits.** The energy check validates fat, carbohydrate and protein only. Sodium (2,400 mg)
and saturated fat (20 g) are **assumed** to follow the same table. This must be verified
against a source before any sodium or saturated-fat rule uses these values.
The table is a named, versioned parameter (`DvReference`), so changing it is one line.

### D2. Sugar stays unknown

No reference was verified for Food.com's sugar %DV, so `sugars_g` is `None`
(unknown, never zero) until one is. Glycaemic work must not use it.

### D3. Food.com dishes are served per recipe serving; no estimated mass (revised)

The first draft required a person to hand-verify a serving mass for every catalogue
recipe. That is replaced:

- A Food.com dish keeps its nutrition **per serving**. Its portion options are multiples of
  a serving (for example 0.5, 1.0, 1.5 servings), each carrying an absolute nutrient vector
  (ADR 0002, ADR 0003).
- `serving_mass_g` stays `None` unless a person verifies it with a recorded source. It is
  optional enrichment, not a precondition for the CSP.
- A mass is never estimated from ingredients: Food.com ingredient lists carry no
  quantities, and USDA portion data covers about 21% of Foundation Foods (USDA EDA).

A mass without a source (or the reverse) is rejected by the model.

### D4. Rows with a data defect are quarantined, not deleted (revised)

A row is **quarantined** (kept, with every reason found, in a separate output) when any
holds:

- the nutrition vector does not have seven finite, non-negative numbers;
- name or ingredients are missing, or the ID is not positive;
- kcal is outside 10 to 1,500 or a macro/sodium %DV exceeds 300 (provisional limits);
- Atwater-implied energy / stated energy is outside 0.75 to 1.25 **and** the absolute gap
  exceeds 10 kcal (checked only when the range check passed). Food.com stores whole-number
  %DV, so rounding fat, carbohydrate and protein by 0.5 %DV each moves implied energy by up
  to about 10 kcal (2.9 + 6.0 + 1.0); for light dishes that rounding dominates the ratio.

The floor was 50 kcal. It is now 10 kcal for every row, because vegetable sides can be
lighter than 50 kcal; the 50 kcal floor moved to classification and applies only to meal
dishes (D5).

Quarantined rows never reach the catalogue, but they are counted by reason in the build
report and written to a review file, so a person can re-admit a row through a curated
override (Stage 2). A row without a course tag is **not** defective: it is *unclassified*
and is handled by role classification (D5), not quarantine.

On the full dataset (old rules, for reference): 231,637 raw, 94,505 with a meal tag. Rows
without a meal tag 113,693; out of range 18,816; energy inconsistent 4,622; malformed
metadata 1. Under the new rules the 113,693 become *unclassified*, not rejected.

### D5. Meal compatibility is derived from culinary role, tags are only evidence (revised)

Four attributes are kept separate, because one rule cannot answer all four:

| Attribute | Question | Values |
|---|---|---|
| Cuisine | Where is it from? | exact-tag cuisines, curated |
| Culinary roles | What does it do in a meal? (several allowed) | `CulinaryRole` |
| Dish class | Can it stand alone? (one value) | COMPLETE_MEAL, REQUIRES_ACCOMPANIMENT, COMPONENT |
| Meal compatibility | Which meals suit it? | derived from role, then tag evidence |

Each record also has `classification_status`: `AUTO`, `CURATED` or `REQUIRES_REVIEW`.
Conflicting evidence (for example `main-dish` on a complete biryani) yields
`REQUIRES_REVIEW`. A model or LLM may *suggest* labels offline for review; it never
decides, and a person signs off. Qwen is not involved in catalogue construction.

The earlier fixed map `main-dish -> DINNER` is retired: a main dish can serve lunch or
dinner.

**Implemented rules (Stage 2, `core/food_data/classification.py`).** Food.com has two
kinds of tag: *course* tags (`main-dish`, `side-dishes`, `salads`, `breads`, `breakfast`)
and *main-ingredient* tags (`vegetables`, `rice`, `pasta`). Roles come from course tags;
ingredient tags only qualify a side (`side-dishes` + `rice` is a STAPLE, `side-dishes` +
`vegetables` a VEGETABLE). A vegetable soup is therefore not a vegetable side.

| Evidence | Result |
|---|---|
| `main-dish` or `one-dish-meal` | MAIN_DISH; COMPLETE_MEAL if `one-dish-meal`, a self-contained tag (pasta, sandwiches, casseroles...) or name word (biryani, noodle, momo...), else REQUIRES_ACCOMPANIMENT |
| `breakfast` / `brunch` | BREAKFAST_BASE, COMPLETE_MEAL |
| `side-dishes`, `salads`, savoury `breads` | STAPLE or VEGETABLE, COMPONENT |
| dessert, drink, sauce, snack, appetizer course only | not a planning dish (AUTO, no roles) |
| meal course next to a non-meal course | REQUIRES_REVIEW (conflict) |
| `soups-stews` only, `lunch` only, unqualified side only, nothing | REQUIRES_REVIEW |
| meal dish below 50 kcal, side above 700 kcal per serving | REQUIRES_REVIEW |

Role to meals: BREAKFAST_BASE and FRUIT suit breakfast; MAIN_DISH, STAPLE, VEGETABLE and
PROTEIN_SOURCE suit lunch and dinner. Curated overrides live in
`Data/curated/classification_overrides.json`; they replace the classification fields
together (status CURATED), or only the cuisines, and keep the tag evidence for audit.
An override that matches no accepted recipe fails the build.

Full-data result (231,637 raw rows): 213,696 accepted, of which 106,332 plannable,
52,151 REQUIRES_REVIEW (written to `<version>_review.json` with `--with-review`) and
55,213 not planning dishes; 17,941 quarantined.

### D6. Selection is stratified; popularity is only a tie-breaker (revised)

Catalogue size is provisional (about 150 to 250 dishes). Selection is reproducible (same
inputs and seed give the same result) and ranks candidates by, in order: nutrition
completeness, diet, cuisine, meal, role, portion availability, then popularity as a
tie-breaker **within a stratum**. Popularity may use training-split interactions only.

**Research dataset versus planning catalogue.** The Transformer trains and evaluates on the
full Food.com chronological split, never on the catalogue. The catalogue is chosen without
held-out interactions. The build report records this as a flag
(`independentOfHeldOutData: true`).

### D7. Coverage is measured statically and by scenario

- *Static:* counts by cuisine, meal, diet, role and dish class.
- *Scenario:* representative synthetic profiles run through Member 2's `filter_candidates`
  and `solve_week` once they exist. No clinical thresholds are invented before Member 2
  supplies sourced rules.

## Consequences

- Nutrition values are per serving in physical units, traceable to a named DV table.
- Nothing is silently dropped: every excluded row is quarantined with reasons or marked
  unclassified.
- Catalogue builds are deterministic and reported (`Data/catalogue/<UTC build time>_catalogue.json`, for example `20261018T153045Z_catalogue.json`).
- The existing v0 fixture (191 recipes) predates D4 to D6 and will be rebuilt.

## Open items needing team approval

1. **Selection is skewed to American recipes** (122 of 191; Indian 3, Thai 2, Chinese 6).
   Needs per-cuisine quotas and a curated seed list for Indian, Nepali, Thai and Chinese
   dishes, since Food.com has no Nepali tag.
2. Final catalogue size and per-meal quotas.
3. Source for sodium and saturated-fat daily values and for sugar.
4. Canonical ID format (`FC_<id>` here) and nutrient key names, shared with Members 2 and 3.
5. Whether Food.com-derived nutrition counts as *known* for hard clinical rules (Member 2).
