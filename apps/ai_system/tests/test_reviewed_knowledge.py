"""Review contracts cannot activate production or infer absence from missing edges."""

import pytest
from pydantic import ValidationError
from test_weekly_contracts import evidence

from savora_ai.core.reasoning.reviewed_knowledge import (
    evaluate_clinical_draft,
    evaluate_reviewed_allergen,
    production_release_admission,
)
from savora_ai.schemas.candidates import _content_digest, validate_contract_json
from savora_ai.schemas.daily import DailySourceReference
from savora_ai.schemas.knowledge import ApprovalStatus
from savora_ai.schemas.reviewed_knowledge import (
    CanonicalIngredientV1,
    ClinicalRuleDraftV1,
    IngredientAllergenEvidenceV1,
    IngredientDerivationV1,
    IngredientMappingReleaseV1,
    IngredientMappingV1,
    MappingReviewV1,
)


def review(approved=True):
    return MappingReviewV1(
        status=ApprovalStatus.APPROVED if approved else ApprovalStatus.PENDING,
        reviewer="fixture-reviewer" if approved else None,
        effective_date="2026-10-22" if approved else None,
        evidence=(evidence(),) if approved else (),
    )


def node(identity, *, present=False, parents=(), complete=True, approved=True, absent=True):
    return CanonicalIngredientV1(
        ingredient_id=identity,
        subingredients_complete=complete,
        derived_from=tuple(
            IngredientDerivationV1(
                parent_id=p, relationship="DERIVED_FROM", review=review(approved)
            )
            for p in parents
        ),
        allergens=(
            IngredientAllergenEvidenceV1(
                allergen_id="fixture-allergen",
                status="PRESENT" if present else "VERIFIED_ABSENT",
                review=review(approved),
            ),
        )
        if absent
        else (),
    )


def release(*, mapping_approved=True, inventory=True, complete=True, nodes=None):
    source = DailySourceReference(source_id="mapping-source", version="1", content_digest="a" * 64)
    return IngredientMappingReleaseV1(
        release_id="fictional-review",
        version="1",
        catalogue_version="1",
        source=source,
        recipe_id="fictional-recipe",
        recipe_version="1",
        source_ingredient_ids=("raw-1",),
        ingredient_inventory_complete=inventory,
        mappings=(
            IngredientMappingV1(
                recipe_id="fictional-recipe",
                recipe_version="1",
                source_ingredient_id="raw-1",
                source_ingredient_name="illustrative ingredient",
                source=source,
                canonical_ingredient_id="a",
                mapping_status="RESOLVED",
                subingredients_complete=complete,
                review=review(mapping_approved),
            ),
        ),
        canonical_ingredients=nodes or (node("a"),),
    )


def evaluate(r):
    return evaluate_reviewed_allergen(
        r, "fixture-allergen", expected_digest=_content_digest(r), catalogue_version="1"
    ).value


def test_review_positive_absence_requires_complete_review():
    r = release()
    assert evaluate(r) == "PASS"
    assert validate_contract_json(IngredientMappingReleaseV1, r.model_dump_json(by_alias=True)) == r
    assert production_release_admission()[0].value == "UNKNOWN"


@pytest.mark.parametrize(
    "updates",
    [
        dict(mapping_approved=False),
        dict(inventory=False),
        dict(complete=False),
        dict(nodes=(node("a", absent=False),)),
        dict(nodes=(node("a", parents=("missing",)),)),
        dict(nodes=(node("a", approved=False),)),
    ],
)
def test_missing_unapproved_incomplete_information_is_unknown(updates):
    assert evaluate(release(**updates)) == "UNKNOWN"


def test_derived_chain_known_fail_dominates_incomplete_information():
    r = release(
        inventory=False,
        nodes=(
            node("a", parents=("b",), absent=False),
            node("b", parents=("c",), absent=False),
            node("c", present=True),
        ),
    )
    assert evaluate(r) == "FAIL"
    assert evaluate(release(nodes=(node("a", parents=("b",)), node("b", present=True)))) == "FAIL"


@pytest.mark.parametrize("axis", ["cycle", "duplicate", "source", "review", "environment"])
def test_malformed_review_material_rejects(axis):
    r = release()
    data = r.model_dump()
    if axis == "cycle":
        data["canonical_ingredients"] = (node("a", parents=("b",)), node("b", parents=("a",)))
    elif axis == "duplicate":
        data["mappings"] = (*r.mappings, *r.mappings)
    elif axis == "source":
        data["mappings"][0]["source"]["version"] = "stale"
    elif axis == "review":
        data["mappings"][0]["review"]["evidence"] = ()
    else:
        data["environment"] = "PRODUCTION"
    with pytest.raises(ValidationError):
        IngredientMappingReleaseV1.model_validate(data)


def test_independent_release_and_catalogue_pins():
    r = release()
    for digest, version in (("b" * 64, "1"), (_content_digest(r), "2")):
        with pytest.raises(ValueError, match="independent"):
            evaluate_reviewed_allergen(
                r, "fixture-allergen", expected_digest=digest, catalogue_version=version
            )


@pytest.mark.parametrize("condition", ["HYPERTENSION", "TYPE_2_DIABETES", "DYSLIPIDEMIA"])
def test_clinical_drafts_cannot_be_enabled(condition):
    draft = ClinicalRuleDraftV1(condition=condition, nutrient=None, candidate_sources=())
    assert evaluate_clinical_draft(draft).value == "UNKNOWN"
    for updates in (dict(activation="ACTIVE"), dict(threshold="2300"), dict(approval="APPROVED")):
        with pytest.raises(ValidationError):
            ClinicalRuleDraftV1.model_validate(draft.model_dump() | updates)
