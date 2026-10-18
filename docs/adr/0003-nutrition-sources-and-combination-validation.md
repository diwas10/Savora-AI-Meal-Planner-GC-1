# ADR 0003: Nutrition sources, common representation and combination validation

- **Status:** Proposed by Member 1 for team approval (Member 2 depends on the contract).
- **Date:** 2026-10-18
- **Owner:** Member 1
- **Relates to:** ARCHITECTURE.md sections 5, 8; ADR 0001; ADR 0002

## Context

Two nutrition sources exist: Food.com (derived from kcal and %DV, per serving, mass
unknown) and USDA (measured, per 100 g). They differ in unit and in how far they can be
trusted. A meal mixes dishes from both, and the architecture says unknown nutrition is
never zero and unsafe unknowns never pass.

## Decisions

### D1. Nutrition source is chosen by identity, not by precedence

A Food.com recipe such as "homemade chicken curry with coconut milk" and a USDA record
"Chicken curry, prepared" may describe different preparations. Automatically replacing the
first with the second can add error. Therefore:

- A dish keeps its **own source** unless the USDA record is the *same food*
  (`identity_match = EXACT`), decided by a curated `fdc_id` list: cooked rice, roti,
  chapati, naan, plain lentils and similar staples.
- A USDA analogue is used **only as a plausibility cross-check**, with mass-independent
  ratios (for example energy per gram of protein), and produces a flag, never a value.
- Each nutrient value carries `source` (`FOODCOM_DERIVED`, `USDA_FNDDS`, `USDA_SR_LEGACY`,
  `USDA_FOUNDATION`, `CURATED`) and `identity_match`.

### D2. One common representation for the CSP

Every portion option carries its **absolute nutrient vector** for that quantity, for
example `{energyKcal: 545, proteinG: 24, ...}`. `basis` is provenance and takes one of:

- `PER_SERVING`: a quantity expressed in recipe servings;
- `PER_100_G`: a quantity expressed in grams of a USDA food.

The CSP only sums vectors. Worked example: dal 1.0 serving = 350 kcal (Food.com) plus
cooked rice 150 g = 195 kcal (USDA, 130 kcal per 100 g) gives 545 kcal, without any
curry mass. The architecture contract must therefore allow `PER_SERVING` next to
`PER_100_G` (to be agreed with Member 2).

### D3. Unknown stays unknown, per nutrient

Each nutrient is a number or `None`. `None` is never converted to 0, and sugar from
Food.com stays `None` (ADR 0001 D2).

### D4. Combination-level nutrition validation (a pipeline stage)

After combinations are built, each is validated before handoff:

1. **Sum per nutrient.** `known + known = known`; any `None` component makes that nutrient
   of the combination `None`.
2. **Weakest source wins.** The combination's source tier is its lowest-trust
   component's tier. One USDA staple never makes a combination "verified".
3. **Completeness rule.** A combination is `FULLY_KNOWN` only if every nutrient required
   by the active rules is known for every component. Otherwise it is `PARTIAL`, and
   whether a `PARTIAL` combination may pass a hard clinical rule is Member 2's decision.
4. **Sanity.** Combination energy must agree with the sum of its components' energy within
   a tolerance, and fall inside a plausible meal range.

This is a formal acceptance test before the catalogue is handed to Member 2.

## Consequences

- No silent precedence rule can overwrite a dish with a different food.
- The CSP stays simple (sums vectors) and independent of unknown masses.
- Provenance is preserved per component, so explanations can say where each number came
  from.

## Open items needing team approval

1. `PER_SERVING` next to `PER_100_G` in the CSP contract (Member 2).
2. Whether `FOODCOM_DERIVED` counts as known for hard clinical rules (Member 2).
3. Verification source for sodium and saturated-fat daily values; hand-check of sodium on
   5 to 10 recipes before any sodium rule uses it.
4. The curated USDA staple list (`fdc_id`) and its reviewer.
5. Nutrient key names (the PDF omits saturated fat from the canonical list).
