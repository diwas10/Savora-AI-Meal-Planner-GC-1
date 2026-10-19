# ADR 0002: Meal composition scope and portion presets

- **Status:** Proposed by Member 1 for team approval (Member 2 consumes the output).
- **Date:** 2026-10-18
- **Owner:** Member 1 (Meal Composition Engine, portion definitions)
- **Relates to:** ARCHITECTURE.md sections 6, 8; ADR 0001; ADR 0003

## Context

The product serves a real meal such as rice + dal + vegetable, not one dish. But the CSP
search grows exponentially with the number of free portion choices: three components with
five portion levels each already give 125 configurations per candidate meal, for hundreds
of candidates, across 21 slots. The deadline is close, so the scope must be bounded.

## Decisions

### D1. A meal has 1 to 3 dishes (N <= 3)

Allowed shapes are listed in a **template table stored as data**, not hard-coded:

- one `COMPLETE_MEAL` dish (for example biryani);
- staple + main;
- staple + main + vegetable.

A `REQUIRES_ACCOMPANIMENT` dish must be paired with a compatible role. Pairing rules
(for example dal with rice or roti) are a curated list that a person reviews.

### D2. Portions are curated configurations, not proportional scaling

Scaling every component by the same factor cannot trade rice for dal, which a high-protein,
low-carbohydrate user needs. Instead every combination gets a small, fixed set of presets
(about four), built from **per-role rules** defined once:

| Preset | MAIN_DISH | STAPLE | VEGETABLE |
|---|---|---|---|
| STANDARD | 1.0 serving | standard portion | standard portion |
| HIGHER_PROTEIN | 1.5 servings | small | standard |
| LOWER_CARB | 1.25 servings | smallest | large |
| HIGHER_ENERGY | 1.25 servings | large | standard |

The rules are provisional and documented, so they can be reviewed and changed in one
place. The CSP chooses among about four configurations per candidate, not 125.

### D3. Each component keeps its own unit

A Food.com dish is measured in servings; a USDA staple in grams. Each preset is a list of
`(component, quantity, unit)` and carries the **total nutrient vector** of the meal
(ADR 0003). The CSP only adds vectors, so an unknown curry mass never matters.

### D4. Size caps

At most one combination per distinct (template, component set); a global cap on the
number of combinations passed to the Transformer and CSP, set after measuring solver
time with Member 2. Caps are named constants.

### D5. Composition is for planning only

A standalone craving does not use the composer or the CSP (AGENTS.md invariant). The
composer serves planned meals and planned substitutions.

## Implemented (Stages 6 and 8)

- **Templates as data** (`Data/curated/meal_templates.json`): `ONE_DISH`, `MAIN_STAPLE`,
  `MAIN_STAPLE_VEGETABLE`, `BREAKFAST`, `BREAKFAST_FRUIT`, `BREAKFAST_PROTEIN`. A role may
  fill one slot only; at most 3 slots.
- **Pairings as data** (`Data/curated/pairings.json`): per cuisine, the verified USDA
  staples a main may be served with (Indian: rice, brown rice, roti, naan; Nepali: rice,
  roti; Thai: rice, rice noodles; and so on). A vegetable side must share the main's
  cuisine or be cuisine-neutral; same-cuisine sides come first. A breakfast add-on whose
  ingredient is already in the base is skipped (no boiled egg with an omelette).
- **Presets as steps.** Each preset moves each slot a number of steps from the dish's
  standard portion along that dish's own options (Food.com 0.5/0.75/1/1.25/1.5 servings;
  roti 1/2/3/4 pieces), clamped to the ends. HIGHER_PROTEIN: main +2, staple -1.
  LOWER_CARB: main +1, staple smallest, vegetable +1. HIGHER_ENERGY: main +1, staple +1.
  A fifth preset, **LOWER_ENERGY** (everything -1 except vegetables +1), was added for
  weight-loss goals. Presets that produce an identical portion tuple are merged, so a
  meal has 1 to 5 configurations (about 4.4 on average).
- **IDs.** `C_<templateId>__<dishId>__...` (the template is part of the ID: a frittata as a
  lunch ONE_DISH and as a BREAKFAST are different meals). Configuration:
  `<combinationId>#<PRESET>`. This answers open item 4.
- **Caps** (`CompositionLimits`): 2 staples per main, 1 vegetable side per main and staple,
  2 add-ons per breakfast base, chosen by a seeded hash; exceeding 600 meals per meal type
  is an error, never a silent cut.
- **Result:** 475 meals (breakfast 179, lunch and dinner 300 each), 2,101 configurations
  after validation (ADR 0003 D4).

## Consequences

- Search size is bounded and predictable.
- Presets are explainable: "less rice, more dal" is a rule a reviewer can read.
- Presets are not an optimum: a user may get a plan slightly off the mathematically best
  portion split. This is accepted for the deadline.

## Open items needing team approval

1. Preset rule values (the table above is provisional).
2. Final N cap and combination cap, after Member 2 measures solver time.
3. Curated pairing list and the list of complete-meal dishes.
4. Combination ID format (`C_DAL_RICE` versus `COMBO_101` in the PDF) and whether the
   preset is part of the ID.
