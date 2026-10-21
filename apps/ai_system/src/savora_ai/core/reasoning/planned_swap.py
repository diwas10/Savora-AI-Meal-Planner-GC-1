"""Stable public saved-plan, validation and selection API facade."""

from collections.abc import Callable
from time import monotonic

from savora_ai.core.reasoning.swap_material import (
    _context_ref as _context_ref,
)
from savora_ai.core.reasoning.swap_material import (
    _facts_projection as _facts_projection,
)
from savora_ai.core.reasoning.swap_material import (
    _knowledge_ref as _knowledge_ref,
)
from savora_ai.core.reasoning.swap_material import (
    _ref as _ref,
)
from savora_ai.core.reasoning.swap_material import (
    _same as _same,
)
from savora_ai.core.reasoning.swap_material import (
    _SavedInputs as _SavedInputs,
)
from savora_ai.core.reasoning.swap_material import (
    _source_ref as _source_ref,
)
from savora_ai.core.reasoning.swap_material import (
    _SwapInputs as _SwapInputs,
)
from savora_ai.core.reasoning.swap_material import (
    build_swap_check_manifest as build_swap_check_manifest,
)
from savora_ai.core.reasoning.swap_material import (
    validate_saved_plan_material as validate_saved_plan_material,
)
from savora_ai.core.reasoning.swap_validation import validate_swap as validate_swap
from savora_ai.schemas.candidates import (
    CandidateRecipeFacts,
    RuleContext,
)
from savora_ai.schemas.daily import MealOptionReference
from savora_ai.schemas.knowledge_base import KnowledgeBaseSnapshot
from savora_ai.schemas.planned_swap import (
    PlannedSwapRequest,
    PlannedSwapSourceSnapshot,
    PlannedSwapWorkflowBridge,
    SavedPlanLockInventory,
    SavedPlanMaterial,
    SwapReplacementDomain,
    SwapSelectionLimits,
    SwapTargetPermission,
    SwapValidationLimits,
    SyntheticSwapRanking,
)
from savora_ai.schemas.swap_proof import (
    ComputedSwapCertificate as ComputedSwapCertificate,
)
from savora_ai.schemas.swap_proof import (
    ComputedSwapSelectionResult,
    ComputedSwapValidationResult,
    SwapProofCheck,
)


def verify_swap_validation(
    result: ComputedSwapValidationResult,
    *,
    request: PlannedSwapRequest,
    replacement: MealOptionReference,
    saved_plan: SavedPlanMaterial,
    locks: SavedPlanLockInventory,
    permission: SwapTargetPermission,
    candidates: tuple[CandidateRecipeFacts, ...],
    knowledge: KnowledgeBaseSnapshot,
    context: RuleContext,
    sources: PlannedSwapSourceSnapshot,
    bridge: PlannedSwapWorkflowBridge,
    limits: SwapValidationLimits,
    clock: Callable[[], float] = monotonic,
) -> SwapProofCheck:
    """Public independently supplied-authority proof API; see the dedicated checker."""
    from savora_ai.core.reasoning.swap_proof import verify_swap_validation as check

    return check(
        result,
        request=request,
        replacement=replacement,
        saved_plan=saved_plan,
        locks=locks,
        permission=permission,
        candidates=candidates,
        knowledge=knowledge,
        context=context,
        sources=sources,
        bridge=bridge,
        limits=limits,
        clock=clock,
    )


def select_swap_replacement(
    request: PlannedSwapRequest,
    *,
    domain: SwapReplacementDomain,
    ranking: SyntheticSwapRanking,
    saved_plan: SavedPlanMaterial,
    locks: SavedPlanLockInventory,
    permission: SwapTargetPermission,
    candidates: tuple[CandidateRecipeFacts, ...],
    knowledge: KnowledgeBaseSnapshot,
    context: RuleContext,
    sources: PlannedSwapSourceSnapshot,
    bridge: PlannedSwapWorkflowBridge,
    limits: SwapSelectionLimits,
    clock: Callable[[], float] = monotonic,
) -> ComputedSwapSelectionResult:
    """Select from an independently accepted fixed domain; see the B2 module."""
    from savora_ai.core.reasoning.swap_selection import select_swap_replacement as select

    return select(
        request,
        domain=domain,
        ranking=ranking,
        saved_plan=saved_plan,
        locks=locks,
        permission=permission,
        candidates=candidates,
        knowledge=knowledge,
        context=context,
        sources=sources,
        bridge=bridge,
        limits=limits,
        clock=clock,
    )


def verify_swap_selection(
    result: ComputedSwapSelectionResult,
    *,
    request: PlannedSwapRequest,
    domain: SwapReplacementDomain,
    ranking: SyntheticSwapRanking,
    saved_plan: SavedPlanMaterial,
    locks: SavedPlanLockInventory,
    permission: SwapTargetPermission,
    candidates: tuple[CandidateRecipeFacts, ...],
    knowledge: KnowledgeBaseSnapshot,
    context: RuleContext,
    sources: PlannedSwapSourceSnapshot,
    bridge: PlannedSwapWorkflowBridge,
    limits: SwapSelectionLimits,
    clock: Callable[[], float] = monotonic,
) -> SwapProofCheck:
    from savora_ai.core.reasoning.swap_proof import verify_swap_selection as check

    return check(
        result,
        request=request,
        domain=domain,
        ranking=ranking,
        saved_plan=saved_plan,
        locks=locks,
        permission=permission,
        candidates=candidates,
        knowledge=knowledge,
        context=context,
        sources=sources,
        bridge=bridge,
        limits=limits,
        clock=clock,
    )
