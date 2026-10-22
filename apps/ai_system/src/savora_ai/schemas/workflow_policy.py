"""Closed synthetic workflow policy registrations; never caller-owned authority.

The definition digest uses the existing KB canonical JSON encoding over the full
RuleDefinition. Registry contents are fixed for this token; changing them requires
a new policy version. These fictional registrations cannot enable production KBs.
"""

from dataclasses import dataclass
from typing import Literal

from savora_ai.schemas.knowledge import RuleScope

WORKFLOW_POLICY_V1 = "synthetic-workflow-scopes.v1"
WORKFLOW_POLICY_V2 = "synthetic-workflow-scopes.v2-registered-swap"
WorkflowPolicyVersion = Literal[
    "synthetic-workflow-scopes.v1", "synthetic-workflow-scopes.v2-registered-swap"
]


@dataclass(frozen=True, slots=True)
class RegisteredWorkflowExtension:
    rule_id: str
    version: str
    scope: RuleScope
    definition_digest: str
    workflows: tuple[Literal["PLANNED_SWAP"], ...]


REGISTERED_SWAP_EXTENSIONS = (
    RegisteredWorkflowExtension(
        rule_id="synthetic-swap-week-quantity-cap",
        version="1",
        scope=RuleScope.WEEK,
        definition_digest="0b9d9ead8206504f86f2385550184b743fdf398a38e10bb0c7c59a2bdca9de5d",
        workflows=("PLANNED_SWAP",),
    ),
)
