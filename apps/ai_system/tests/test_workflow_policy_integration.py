"""Policy admission, independent manifests and literal incremental obligations.

These tests do not run the unfinished swap proof/resource test suite.
"""

import inspect

import pytest
from pydantic import ValidationError
from swap_oracle import arguments, make_case
from test_planned_swap_contracts import rebuild
from test_workflow_policy import EXTENSION, V2

from savora_ai.core.reasoning.daily import build_day_check_manifest
from savora_ai.core.reasoning.filtering import filter_candidates
from savora_ai.core.reasoning.manifest import build_expected_check_manifest
from savora_ai.core.reasoning.planned_swap import build_swap_check_manifest, validate_swap
from savora_ai.core.reasoning.swap_checks import _admit, _schedule
from savora_ai.core.reasoning.weekly import build_week_check_manifest, evaluate_weekly_trial
from savora_ai.schemas import planned_swap as s
from savora_ai.schemas.daily import DailySourceSnapshot
from savora_ai.schemas.filtering import ExpectedCheckManifest
from savora_ai.schemas.knowledge_base import KnowledgeWorkflow
from savora_ai.schemas.reasoning import RuleStatus
from savora_ai.schemas.weekly import _daily_request


@pytest.fixture(scope="module")
def case():
    return make_case(swap_only=True, week_limit=44)


@pytest.mark.parametrize("workflow", tuple(KnowledgeWorkflow))
def test_policy_propagates_to_all_recipe_workflows(case, workflow):
    context = rebuild(case["context"], workflow=workflow)
    candidate = case["sources"].candidates[0]
    manifest = build_expected_check_manifest(case["knowledge"], candidate, context)
    assert manifest.workflow_policy_version == V2
    checks = (*manifest.required_checks, *manifest.deferred_checks)
    assert (EXTENSION in {r.rule_id for r in checks}) == (
        workflow is KnowledgeWorkflow.PLANNED_SWAP
    )
    filtered = filter_candidates((candidate,), knowledge=case["knowledge"], context=context)
    assert filtered.decisions[0].status is RuleStatus.PASS
    assert filtered.decisions[0].resolution.manifest == manifest


def test_complete_swap_manifest_is_independently_reconstructed(case):
    manifest = build_swap_check_manifest(**case)
    assert tuple(r.rule_id for r in manifest.required_checks) == (
        "combination",
        "day-amount",
        "day-complete",
        "recipe",
        EXTENSION,
        "week-amount",
        "week-complete",
        "week-repetition",
    )
    body = manifest.model_dump(exclude={"content_digest"})
    body["required_checks"] = tuple(r for r in manifest.required_checks if r.rule_id != EXTENSION)
    with pytest.raises(ValidationError):
        s.ExpectedSwapCheckManifest.build(body)


@pytest.mark.parametrize("axis", ("context", "manifest", "source"))
def test_policy_and_cross_workflow_transplants(case, axis):
    context, kb = case["context"], case["knowledge"]
    if axis == "context":
        with pytest.raises(ValidationError):
            build_expected_check_manifest(
                kb,
                case["sources"].candidates[0],
                rebuild(context, workflow_policy_version="synthetic-workflow-scopes.v1"),
            )
    elif axis == "manifest":
        from savora_ai.core.reasoning.evaluation import evaluate_rule_checks
        from savora_ai.schemas.candidates import _content_digest
        from savora_ai.schemas.filtering import _ManifestContent

        manifest = build_expected_check_manifest(kb, case["sources"].candidates[0], context)
        body = _ManifestContent.model_validate(
            manifest.model_dump(exclude={"manifest_id", "manifest_version", "content_digest"})
            | dict(workflow_policy_version="synthetic-workflow-scopes.v1")
        )
        digest = _content_digest(body)
        forged = ExpectedCheckManifest.model_validate(
            body.model_dump()
            | dict(
                content_digest=digest,
                manifest_id="manifest-" + digest,
                manifest_version="synthetic-manifest.v1:" + digest,
            )
        )
        with pytest.raises(ValidationError):
            evaluate_rule_checks(kb, case["sources"].candidates[0], context, forged)
    else:
        original = case["saved_plan"].snapshot.original_sources.daily_source
        with pytest.raises(ValidationError):
            DailySourceSnapshot.build(
                original.model_dump(exclude={"content_digest"}) | dict(context=context)
            )
        with pytest.raises((ValidationError, s.SwapBoundaryError)):
            validate_swap(
                **(arguments(case) | dict(context=case["saved_plan"].snapshot.original_context))
            )


def test_existing_day_week_adapters_keep_their_workflows(case):
    original = case["saved_plan"].snapshot
    request = original.original_request
    day_request = _daily_request(request, request.days[0])
    day = build_day_check_manifest(
        day_request,
        knowledge=case["knowledge"],
        context=original.original_context,
        sources=original.original_sources.daily_source,
    )
    week = build_week_check_manifest(
        request,
        knowledge=case["knowledge"],
        context=original.original_context,
        sources=original.original_sources,
    )
    assert EXTENSION not in {
        r.rule_id for r in (*day.required_checks, *day.deferred_checks, *week.required_checks)
    }
    result = evaluate_weekly_trial(
        request=request,
        trial=original.original_trial,
        candidates=original.original_candidates,
        knowledge=case["knowledge"],
        context=original.original_context,
        sources=original.original_sources,
    )
    assert result.status is RuleStatus.PASS


@pytest.mark.parametrize("enabled,expected", ((None, RuleStatus.UNKNOWN), (False, RuleStatus.PASS)))
def test_unknown_and_evidenced_not_applicable(enabled, expected):
    c = make_case(swap_only=True, enabled=enabled)
    filtered = filter_candidates(
        c["sources"].candidates, knowledge=c["knowledge"], context=c["context"]
    )
    assert filtered.decisions[0].status is expected
    # The mandatory extension remains in the deferred inventory in both cases.
    assert EXTENSION in {
        r.rule_id for r in filtered.decisions[0].resolution.manifest.deferred_checks
    }
    if enabled is False:
        assert all(
            e.reason.endswith("NOT_APPLICABLE") and e.applicability_evidence
            for e in filtered.decisions[0].trace.evaluations
        )
    outcome = validate_swap(**arguments(c), clock=lambda: 0.0)
    assert outcome.outcome.value == ("INSUFFICIENT_DATA" if enabled is None else "VALID")
    assert outcome.certificate is not None
    assessment = next(
        e for e in outcome.certificate.result.week.trace.evaluations if e.rule.rule_id == EXTENSION
    )
    assert assessment.status is RuleStatus.UNKNOWN
    assert assessment.applicability.value == ("UNKNOWN" if enabled is None else "NOT_APPLICABLE")
    assert assessment.applicability_evidence


def test_literal_additional_predicate_and_reservation_cost(case):
    inputs = _admit(arguments(case))
    schedule = _schedule(inputs)
    # Three distinct phase-local option preparations: 3 recipe + 3 combination
    # obligations, 14 DAY passes x 2, original WEEK 3 and resulting WEEK 4.
    assert schedule.execution.predicate_obligations == 3 + 3 + 28 + 3 + 4 == 41
    assert schedule.verification.predicate_obligations == 41
    assert sum(o.reserved.predicate_obligations for o in schedule.plan.operations) == 82
    assert schedule.execution.day_assessments == schedule.verification.day_assessments == 14
    assert schedule.execution.week_assessments == schedule.verification.week_assessments == 2
    assert not schedule.execution.domain_visits and not schedule.execution.ordering_items
    common = _schedule(_admit(arguments(make_case())))
    assert common.execution.predicate_obligations == 40


def test_public_authority_signature_is_unchanged():
    assert tuple(inspect.signature(validate_swap).parameters) == (
        "request",
        "replacement",
        "saved_plan",
        "locks",
        "permission",
        "candidates",
        "knowledge",
        "context",
        "sources",
        "bridge",
        "limits",
        "clock",
    )
    assert (
        inspect.signature(validate_swap).parameters["saved_plan"].kind
        is inspect.Parameter.KEYWORD_ONLY
    )
