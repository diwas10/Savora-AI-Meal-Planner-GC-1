# ADR 0006: Interim portion fitting before the CSP

- **Status:** Proposed (Member 1), interim until Member 2's nutrient DAY rules are integrated
- **Date:** 2026-10-22
- **Owner:** Member 1 (planning pipeline); Member 2 owns the CSP that replaces this
- **Relates to:** ARCHITECTURE.md section 8 (CSP and portions); ADR 0002 (portion presets);
  `apps/ai_system/src/savora_ai/core/pipelines/planning.py::_fit_portions`

## Context

ARCHITECTURE.md section 8 has the CSP choose each slot's portion configuration against
the daily energy and protein bounds. The GC1 stand-in KB carries structural DAY and WEEK
rules only, and Member 2's solver orders a slot's options by option ID, not by rank. The
planner therefore offered ONE option per slot, always at its STANDARD portion, and the
planned days fell well below or above the user's estimated targets. On catalogue
20261021T073631Z a strict Indian vegetarian profile with a 1,710-1,890 kcal band had 0 of
7 days in the band; a mixed profile with a 1,900-2,100 kcal band also had 0.

## Decision

Until the CSP enforces nutrient DAY rules, the planner sizes portions **before** the CSP:

1. The backend passes the profile version's targets to the AI layer as `DayTargets`:
   the energy band (`energyKcal` min, target, max) and the protein minimum (`protein_g`
   min) from the stored `NutritionTargets` snapshot. Without a snapshot nothing changes.
2. For each day, `_fit_portions` tries every combination of the three meals' measurable
   presets (at most 5^3 = 125) and keeps the lowest cost, compared in order:
   1. kcal outside the band plus 4 kcal per gram of protein below the minimum;
   2. the number of resized (non-STANDARD) meals, so a day already in the band keeps
      STANDARD portions;
   3. the distance from the energy target.
3. The meals themselves never change: ranking and rotation choose the meals, fitting
   chooses only their presets. The CSP then verifies the 21 fitted options exactly as
   before, still one option per slot.
4. A swap resizes only the new meal (`vary=(slot,)`); the other 20 keep their saved
   options, portions included (section 4.4).
5. Results never claim the targets are verified: the plan message reports how many of
   the 7 days fall within the estimated energy band, and the UI keeps calling the
   targets estimates.

## Measured effect (catalogue 20261021T073631Z, before the CSP)

| Profile and band | STANDARD days in band | Fitted days in band | Meals resized |
|---|---|---|---|
| Mixed, 1,900-2,100 kcal | 0 / 7 | 5 / 7 | 18 / 21 |
| Mixed, 1,520-1,680 kcal | 2 / 7 | 6 / 7 | 7 / 21 |
| Mixed, 2,470-2,730 kcal | 1 / 7 | 1 / 7 | 18 / 21 |
| Strict Indian vegetarian, 1,710-1,890 kcal | 0 / 7 | 6 / 7 | 17 / 21 |
| Strict Nepali, 2,090-2,310 kcal | 1 / 7 | 7 / 7 | 14 / 21 |

The presets reach about 0.75x to 2x of a meal's standard energy. A high target that the
ranked meals cannot reach even at their largest presets stays below the band; that is
reported, not hidden.

## Consequences

- This is a **deviation from section 8**: the CSP does not choose portions, so the
  fitted days are not proven to meet the band, and sodium, carbohydrate and fat are not
  traded against energy. Day totals remain reported values.
- Fitting is greedy per day over a fixed meal rotation; a different meal choice might
  fit better. Accepted for the deadline.
- When Member 2's seven-nutrient DAY/WEEK contracts and ranked value order are
  integrated, each slot offers all its measurable presets, the band becomes a DAY rule,
  and `_fit_portions` is deleted. The pipeline signatures do not change.

## Update 2026-10-23: Member 2's native nutrients (PR #20)

PR #20 adds seven-nutrient DAY/WEEK bands and a ranked value order to weekly search v2,
and is merged into this branch. Fitting stays for now, because:

- the nutrient search checks bands only at complete weeks ("native nutrient bound pruning
  is deferred"), so a day outside its band is found only after all 21 slots are assigned,
  and backtracking over several presets per slot grows exponentially;
- a `WeeklyNutrientContractV2` holds at most 75 options, fewer than the up to 105 that
  five presets on 21 slots need.

When band pruning lands, offer the fitted preset first (highest priority) and the other
measurable presets after it, make the band a DAY rule, and delete `_fit_portions`.

## Open items needing team approval

1. The cost weights (4 kcal per gram of protein shortfall) and whether carbohydrate and
   fat ranges should also count before the CSP takes over.
2. Whether to show per-day "within band" status in the UI rather than only the summary
   count in the plan message.
