# ADR 0001: Catalogue v0 and nutrition basis

- **Status:** Proposed by Member 1 for team approval. Not yet jointly approved.
- **Date:** 2026-10-18
- **Owner:** Member 1 (Food.com/USDA normalization, portion definitions)
- **Relates to:** ARCHITECTURE.md sections 3, 5, 8, 15; Food.com EDA (`eda/food.com_eda.md`)

## Context

The CSP needs nutrition per reference quantity and discrete gram portions (ARCHITECTURE.md
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
macros (`9*fat + 4*carbohydrate + 4*protein`) was compared with the stated kcal:

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

### D3. Serving mass is verified by a person, per catalogue recipe

Options considered:

1. **Estimate mass from ingredients through USDA portions.** Rejected as the sole method:
   USDA portion data covers about 21% of Foundation Foods (USDA EDA), and Food.com
   ingredient lists carry no quantities.
2. **Keep nutrition per serving and leave mass unknown.** Rejected: the CSP and the
   architecture's `PER_100_G` contract need a mass.
3. **Hand-verify the serving mass of every catalogue recipe (chosen).** Possible because
   the catalogue is small. An estimate may be used as a starting draft only.

Until a mass is verified, `serving_mass_g` is `None` and `per_100g()` returns `None`.
A mass without a source (or the reverse) is rejected by the model.

### D4. Eligibility filters for a catalogue candidate (provisional)

A row is rejected, with a recorded reason, unless all hold:

- the nutrition vector has seven finite, non-negative numbers;
- name and ingredients are present and the ID is positive;
- 50 <= kcal <= 1,500 and every macro/sodium %DV <= 300;
- Atwater-implied energy / stated energy is within 0.75 to 1.25;
- the recipe maps to at least one meal type.

On the full dataset: 231,637 raw, **94,505 eligible**. Rejections: no meal type 113,693;
out of range 18,816; energy inconsistent 4,622; malformed metadata 1.

### D5. Meal types come from exact course tags

`breakfast` -> BREAKFAST, `lunch` -> LUNCH, `main-dish` -> DINNER (Food.com has no dinner
tag). A recipe can serve several meals. `side-dishes` and similar are **not** mapped yet:
dish class and culinary roles need curation (ARCHITECTURE.md section 6).

### D6. Catalogue size and selection

Provisional quotas: breakfast 60, lunch 90, dinner 90 (a dish counts once; the build
produced 191). Selection is reproducible: candidates sorted by (has no cuisine label,
SHA-256 of `seed:recipe_id`), seed `savora-catalogue-v0`.

## Consequences

- Nutrition values are per serving in physical units, traceable to a named DV table.
- No recipe may feed the CSP per-100 g contract until its serving mass is verified.
- Catalogue builds are deterministic and reported (`Data/catalogue/catalogue_v0.json`).

## Open items needing team approval

1. **Selection is skewed to American recipes** (122 of 191; Indian 3, Thai 2, Chinese 6).
   Needs per-cuisine quotas or a curated seed list for Indian, Nepali, Thai and Chinese
   dishes, since the product targets those cuisines and Food.com has no Nepali tag.
2. Final catalogue size and per-meal quotas.
3. Source for sodium and saturated-fat daily values and for sugar.
4. Whether `main-dish` is an acceptable proxy for dinner, and how lunch/dinner overlap
   should be handled.
5. Complete-meal versus component classification, which this ADR does not decide.
6. Canonical ID format (`FC_<id>` here) and nutrient key names, shared with Members 2 and 3.
