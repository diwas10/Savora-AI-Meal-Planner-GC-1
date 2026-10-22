"""Integration pipelines: the typed calls the backend makes (one per workflow).

    load_catalogue_export(Path("Data/catalogue"))      startup: catalogue + popularity
    recommend_for_craving(request, profile, bundle)    section 4.3, no composer / CSP
    plan_week(profile, bundle, week_id=, start_date=)  section 4.2, 21 slots via weekly CSP
    suggest_replacements(profile, bundle, current=, slot=, preference=)
                                                       section 4.4: ranked, rule-screened options
    substitute_slot(profile, bundle, current=, slot=)  section 4.4, other slots locked
    suggest_seeds / confirm_seeds / revalidate_seeds   ADR 0005 onboarding seed dishes

Pure functions: no database, network or file I/O after the catalogue is loaded. Every
result carries `safety` (STAND_IN_UNVERIFIED) until Member 2's production KB replaces
`stand_in_kb.py`.
"""

from savora_ai.core.pipelines.catalogue import CatalogueBundle, cuisine_id, load_catalogue_export
from savora_ai.core.pipelines.craving import (
    CravingRecommendation,
    CravingStatus,
    recommend_for_craving,
)
from savora_ai.core.pipelines.onboarding import confirm_seeds, revalidate_seeds, suggest_seeds
from savora_ai.core.pipelines.planning import (
    PlannedMeal,
    PlanStatus,
    ReplacementOption,
    ReplacementOptions,
    WeekPlan,
    plan_week,
    substitute_slot,
    suggest_replacements,
)
from savora_ai.core.pipelines.profile import (
    DayTargets,
    DietPattern,
    PlanningProfile,
    SafetyVerification,
)

__all__ = [
    "CatalogueBundle",
    "CravingRecommendation",
    "CravingStatus",
    "DayTargets",
    "DietPattern",
    "PlanStatus",
    "PlannedMeal",
    "PlanningProfile",
    "ReplacementOption",
    "ReplacementOptions",
    "SafetyVerification",
    "WeekPlan",
    "confirm_seeds",
    "cuisine_id",
    "load_catalogue_export",
    "plan_week",
    "recommend_for_craving",
    "revalidate_seeds",
    "substitute_slot",
    "suggest_replacements",
    "suggest_seeds",
]
