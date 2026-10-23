# ADR 0008: Excluded ingredients block only as main ingredients; allergies always block

- **Status:** Accepted by Member 1 (2026-10-23)
- **Owner:** Member 1 (stand-in profile screen, `pipelines/profile.py`, `pipelines/ingredient_swaps.py`)
- **Relates to:** AGENTS.md "Savora invariants"; ADR 0005 (seed dishes); `pipelines/allergens.py`

## Context

The profile screen blocked any dish whose name or ingredient list mentioned an excluded
ingredient. Onion and garlic are in most Indian and Nepali recipes, so a vegetarian who
excludes them (common for religious or digestive reasons) kept 6 of 54 Indian and Nepali
favourite candidates and few planned meals. Those dishes are routinely cooked without them.

## Decision

1. **Allergies and diet are unchanged:** an allergen blocks a dish in any amount, with
   the derived-allergen table; a missing diet tag blocks. A trace of an allergen can cause
   a reaction, so allergy blocking never depends on how much of the dish it is
   (AGENTS.md: allergy restrictions always apply).
2. **An excluded ingredient blocks only as a MAIN ingredient.** The catalogue has no
   ingredient amounts, so "main" is judged from the data available. A word is main if:
   - it is in the dish name; or
   - it is in the first ingredient line (on Food.com, usually the base); or
   - it is in a third or more of the ingredient lines.
   Structural ingredients (flour, egg, rice, milk, tofu, ...) and words naming an
   allergen group always block.
3. **Otherwise the dish stays,** with a curated swap (onion -> hing, garlic -> ginger or
   hing, ...) or "leave it out". A swap whose own words hit an allergy or another
   exclusion becomes "leave it out".
4. **Every meal says so:**
   - reason `COOK_WITHOUT_EXCLUDED` on plan, swap-option and craving explanations;
   - a "Cook it your way" callout in the meal and recipe sheets;
   - the swaps on favourite-dish cards;
   - a line in the safety notice.
   Nutrition still includes the omitted ingredient (minor by definition) and says so.
5. Favourite-dish suggestions list the chosen cuisines' dishes that fit as they are, then
   those that need a swap, and only then other cuisines (fewer than 3 left).

## Measured (catalogue 20261021T073631Z)

Vegetarian, Mixed, Nepali and Indian, peanut allergy, excluding mushroom, onion, garlic:

| | Before | After |
|---|---|---|
| Indian and Nepali dishes allowed | 12 of 65 | 33 of 65 |
| Favourite candidates in those cuisines | 6 | 25 |
| Allowed dishes containing peanut | 0 | 0 |

## Consequences

- More dishes and meals for users with exclusions; the user cooks the meal without the
  ingredient. The "main" judgement is a heuristic over names and list positions.
- The swap table and the structural list are `ai-review:claude` curation; a person should
  review them, as with the allergen table.
