# Clinical evidence candidates: inactive, not team approved

Retrieved 22 October 2026. No numeric clinical policy is authorized by this inventory.
The team's clinical reviewer must approve the exact population, applicability,
attribute, source/version, threshold and DAY/WEEK interpretation before activation.
Per-meal thresholds cannot be invented by dividing a daily recommendation.

| Condition / candidate source | Date and population | Attribute / native unit | Interpretation and admission |
|---|---|---|---|
| Hypertension: [WHO sodium guideline](https://www.who.int/publications/i/item/9789241504836/) |25 December 2012; adults/children with population-specific guidance | Sodium /mg | Population daily intake guidance; not an approved Savora individualized clinical hard limit. Requires exact reviewer-approved scope and exceptions. |
| Type 2 diabetes: [NIDDK nutrition counseling](https://www.niddk.nih.gov/health-information/professionals/diabetes-discoveries-practice/diabetes-nutrition-counseling) | Professional guidance; individualized care, page revision requires reviewer capture | Carbohydrate, energy and related targets /g,kcal | Supports individual nutrition planning with a dietitian. Does not supply a universal diabetes sugar/carbohydrate cutoff for this system. |
| Dyslipidemia: [WHO saturated and trans-fat guideline](https://www.who.int/publications/i/item/9789240073630) |17 July 2023; adults and children, population prevention context | Saturated fatty acids /energy fraction; derived g would need exact approved energy basis | Public-health guidance; not an approved individualized hard gram threshold. Requires reviewed conversion, applicability and treatment context. |

The existing Member 1 targets-0.2 calculator uses provisional general energy and
meal-share factors with IOM adult AMDR/protein references. It supplies no approved
hypertension, diabetes or dyslipidemia thresholds. General energy/protein bands
must remain GENERAL_TARGET, separate from clinical rules.

`clinical-rule-draft.v1` stores condition, candidate sources and pending review;
threshold is necessarily null, activation is INACTIVE_NOT_AUTHORIZED and
applicability is REQUIRES_CLINICAL_REVIEW. Evaluation returns UNKNOWN. No active
production KB, source-loader registry, reviewer identity or revocation authority
is manufactured. A future production release needs independently selected trusted
sources, exact rule inventories for each workflow, complete evidence, explicit
revocation checks and version-consistent catalogue/target bindings.
