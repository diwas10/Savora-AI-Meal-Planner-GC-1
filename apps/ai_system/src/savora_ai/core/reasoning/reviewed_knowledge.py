"""Bounded review evaluator. No production eligibility or external authorization."""

from savora_ai.schemas.candidates import _content_digest
from savora_ai.schemas.knowledge import ApprovalStatus
from savora_ai.schemas.reasoning import RuleStatus
from savora_ai.schemas.reviewed_knowledge import ClinicalRuleDraftV1, IngredientMappingReleaseV1


def evaluate_reviewed_allergen(
    release: IngredientMappingReleaseV1,
    allergen_id: str,
    *,
    expected_digest: str,
    catalogue_version: str,
) -> RuleStatus:
    """Known reviewed presence FAILs; absence needs complete positive evidence.

    The expected pin must be selected by the server-side reviewer registry. This
    REVIEW_ONLY function never admits a production KB, even if it returns PASS.
    """
    release = IngredientMappingReleaseV1.model_validate(release)
    if (
        _content_digest(release) != expected_digest
        or release.catalogue_version != catalogue_version
    ):
        raise ValueError("review release differs from independent source/catalogue pins")
    nodes = {n.ingredient_id: n for n in release.canonical_ingredients}
    mappings = {m.source_ingredient_id: m for m in release.mappings}
    unknown = not release.ingredient_inventory_complete or not release.source_ingredient_ids
    failed = False
    inspected: set[str] = set()
    pending = []
    for ingredient_id in release.source_ingredient_ids:
        mapping = mappings.get(ingredient_id)
        if (
            mapping is None
            or mapping.mapping_status != "RESOLVED"
            or mapping.review.status is not ApprovalStatus.APPROVED
        ):
            unknown = True
            continue
        unknown |= not mapping.subingredients_complete
        pending.append(mapping.canonical_ingredient_id)
    while pending:
        identity = pending.pop()
        if identity in inspected:
            continue
        inspected.add(identity)
        node = nodes.get(identity)
        if node is None:
            unknown = True
            continue
        unknown |= not node.subingredients_complete
        assertion = next((a for a in node.allergens if a.allergen_id == allergen_id), None)
        if assertion is None or assertion.review.status is not ApprovalStatus.APPROVED:
            unknown = True
        elif assertion.status == "PRESENT":
            failed = True
        elif assertion.status != "VERIFIED_ABSENT":
            unknown = True
        for edge in node.derived_from:
            if edge.review.status is ApprovalStatus.APPROVED:
                pending.append(edge.parent_id)
            else:
                unknown = True
    return RuleStatus.FAIL if failed else RuleStatus.UNKNOWN if unknown else RuleStatus.PASS


def evaluate_clinical_draft(draft: ClinicalRuleDraftV1) -> RuleStatus:
    ClinicalRuleDraftV1.model_validate(draft)
    return RuleStatus.UNKNOWN


def production_release_admission() -> tuple[RuleStatus, str]:
    """No production release registry has been approved; there is no activation flag."""
    return RuleStatus.UNKNOWN, "NOT_AUTHORIZED"
