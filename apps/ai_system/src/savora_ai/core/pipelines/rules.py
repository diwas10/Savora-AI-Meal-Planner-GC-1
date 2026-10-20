"""Recipe-stage Rule Engine call shared by the pipelines (Member 2's filter_candidates).

Only a complete hard PASS is eligible; FAIL and UNKNOWN are both excluded and never shown.
The KB is the GC1 stand-in (stand_in_kb.py) scoped to the recipes being checked.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from savora_ai.core.explainability.explanation import RuleOutcome
from savora_ai.core.meal_composition.member2_adapter import candidate_facts
from savora_ai.core.pipelines.catalogue import CatalogueBundle
from savora_ai.core.pipelines.profile import PlanningProfile
from savora_ai.core.pipelines.stand_in_kb import build_stand_in_knowledge, stand_in_context
from savora_ai.core.reasoning.filtering import filter_candidates
from savora_ai.schemas.knowledge_base import KnowledgeWorkflow
from savora_ai.schemas.reasoning import RuleStatus


@dataclass(frozen=True)
class RuleCheck:
    kb_id: str
    kb_version: str
    eligible_ids: frozenset[str]
    outcomes: dict[str, RuleOutcome]  # every checked recipe, for explanations


def check_recipes(
    bundle: CatalogueBundle,
    profile: PlanningProfile,
    workflow: KnowledgeWorkflow,
    recipe_ids: Sequence[str],
) -> RuleCheck:
    knowledge = build_stand_in_knowledge(bundle, recipe_ids)
    context = stand_in_context(knowledge, profile, workflow)
    candidates = tuple(
        candidate_facts(
            bundle.dishes[i], bundle.version, knowledge.graph_id, knowledge.graph_version
        )
        for i in sorted(set(recipe_ids))
    )
    result = filter_candidates(candidates, knowledge=knowledge, context=context)
    outcomes: dict[str, RuleOutcome] = {}
    for decision in result.decisions:
        evaluations = decision.trace.evaluations
        outcomes[decision.trace.candidate_id] = RuleOutcome(
            status=decision.status.value,
            checked_rules=tuple(e.rule.rule_id for e in evaluations),
            failed_rules=tuple(e.rule.rule_id for e in evaluations if e.status is RuleStatus.FAIL),
            unknown_rules=tuple(
                e.rule.rule_id for e in evaluations if e.status is RuleStatus.UNKNOWN
            ),
            trace_id=decision.trace.manifest_id,
        )
    return RuleCheck(
        kb_id=knowledge.kb_id,
        kb_version=knowledge.version,
        eligible_ids=frozenset(result.eligible_ids),
        outcomes=outcomes,
    )
