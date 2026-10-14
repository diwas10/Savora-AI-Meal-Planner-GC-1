"""Atomic synthetic recipe-stage filtering, complete traces and deterministic explanations."""

from typing import Self

from pydantic import model_validator

from savora_ai.core.reasoning.evaluation import _evaluate_resolved_checks
from savora_ai.core.reasoning.facts import _validated_fact_index, resolve_rule_facts
from savora_ai.core.reasoning.kb import build_knowledge_snapshot
from savora_ai.core.reasoning.manifest import _KnowledgeContextRequest, _mandatory_checks
from savora_ai.schemas.candidates import CandidateRecipeFacts, RuleContext
from savora_ai.schemas.filtering import (
    CandidateFilterDecision,
    FilterCandidatesResult,
    RuleExplanation,
    _evidence_union,
)
from savora_ai.schemas.knowledge_base import KnowledgeBaseSnapshot
from savora_ai.schemas.reasoning import RuleTrace, aggregate_hard_status, is_candidate_eligible


class _FilterRequest(_KnowledgeContextRequest):
    candidates: tuple[CandidateRecipeFacts, ...]

    @model_validator(mode="after")
    def validate_unique_candidates(self) -> Self:
        if len({candidate.recipe_id for candidate in self.candidates}) != len(self.candidates):
            raise ValueError("duplicate candidate IDs are not permitted")
        return self


def filter_candidates(
    candidates: tuple[CandidateRecipeFacts, ...],
    *,
    knowledge: KnowledgeBaseSnapshot,
    context: RuleContext,
) -> FilterCandidatesResult:
    """Only complete recipe-stage hard PASS is eligible; deferred planning stays unresolved.

    All batch DTOs and shared inputs are revalidated before evaluation. Any malformed
    candidate rejects the batch; this function has no external writes or partial results.
    """
    request = _FilterRequest.model_validate(
        {"candidates": candidates, "kb": knowledge, "context": context}
    )
    knowledge = build_knowledge_snapshot(
        request.kb, expected_digest=request.context.expected_kb_digest
    )
    context = request.context
    # Empty batches still require accepted catalogue, evaluator and normalized context.
    _mandatory_checks(knowledge, context)
    _validated_fact_index(context.facts)
    decisions: list[CandidateFilterDecision] = []
    for candidate in sorted(request.candidates, key=lambda item: item.recipe_id):
        resolution = resolve_rule_facts(candidate, knowledge=knowledge, context=context)
        manifest = resolution.manifest
        evaluations = _evaluate_resolved_checks(knowledge, context, resolution)
        trace = RuleTrace(
            candidate_id=candidate.recipe_id,
            context_id=context.context_id,
            manifest_id=manifest.manifest_id,
            manifest_version=manifest.manifest_version,
            required_checks=manifest.required_checks,
            evaluations=evaluations,
        )
        indexed = {item.fact.fact_id: item for item in resolution.facts}
        explanations: list[RuleExplanation] = []
        for evaluation in evaluations:
            facts = tuple(indexed[name] for name in sorted(evaluation.rule.required_facts))
            explanations.append(
                RuleExplanation(
                    manifest_id=manifest.manifest_id,
                    manifest_version=manifest.manifest_version,
                    manifest_digest=manifest.content_digest,
                    candidate_id=manifest.candidate_id,
                    candidate_version=manifest.candidate_version,
                    candidate_digest=manifest.candidate_digest,
                    context_id=manifest.context_id,
                    context_version=manifest.context_version,
                    context_digest=manifest.context_digest,
                    kb_id=manifest.kb_id,
                    kb_version=manifest.kb_version,
                    kb_digest=manifest.kb_digest,
                    evaluation=evaluation,
                    facts=facts,
                    evidence=_evidence_union((evaluation, facts)),
                )
            )
        decisions.append(
            CandidateFilterDecision(
                resolution=resolution,
                trace=trace,
                status=aggregate_hard_status(trace),
                explanations=tuple(explanations),
            )
        )
    return FilterCandidatesResult(
        kb_id=knowledge.kb_id,
        kb_version=knowledge.version,
        kb_digest=knowledge.content_digest,
        context=context,
        decisions=tuple(decisions),
        eligible_ids=tuple(
            item.resolution.manifest.candidate_id
            for item in decisions
            if is_candidate_eligible(item.status)
        ),
        excluded_ids=tuple(
            item.resolution.manifest.candidate_id
            for item in decisions
            if not is_candidate_eligible(item.status)
        ),
    )
