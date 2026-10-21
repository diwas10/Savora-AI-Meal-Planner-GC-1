"""Pure saved-material admission and independently checked single-swap validation."""

from collections.abc import Callable
from time import monotonic
from typing import Any, Self

from pydantic import ValidationError, model_validator

from savora_ai.core.reasoning.kb import build_knowledge_snapshot
from savora_ai.core.reasoning.manifest import (
    _KnowledgeContextRequest,
    _mandatory_checks,
    _ManifestRequest,
)
from savora_ai.schemas.candidates import (
    CandidateRecipeFacts,
    RuleContext,
    _canonical_content,
)
from savora_ai.schemas.daily import MealOptionReference
from savora_ai.schemas.knowledge_base import KnowledgeBaseSnapshot
from savora_ai.schemas.planned_swap import (
    ExpectedSwapCheckManifest,
    PlannedSwapRequest,
    PlannedSwapSourceSnapshot,
    PlannedSwapWorkflowBridge,
    SavedPlanContractCheck,
    SavedPlanLockInventory,
    SavedPlanMaterial,
    SwapReference,
    SwapReplacementDomain,
    SwapSelectionLimits,
    SwapTargetPermission,
    SwapValidationLimits,
    SwapWork,
    SyntheticSwapRanking,
    _recipe_reference,
    _slot_digests,
    _SwapModel,
)
from savora_ai.schemas.swap_proof import (
    ComputedSwapCertificate,
    ComputedSwapSelectionResult,
    ComputedSwapValidationResult,
    SwapOutcome,
    SwapProofCheck,
)
from savora_ai.schemas.weekly import WeeklySourceSnapshot


def _context_ref(context: RuleContext) -> SwapReference:
    return SwapReference(
        record_id=context.context_id, version=context.version, content_digest=context.content_digest
    )


def _knowledge_ref(knowledge: KnowledgeBaseSnapshot) -> SwapReference:
    return SwapReference(
        record_id=knowledge.kb_id,
        version=knowledge.version,
        content_digest=knowledge.content_digest,
    )


def _ref(record: Any) -> SwapReference:
    return SwapReference(
        record_id=record.record_id, version=record.version, content_digest=record.content_digest
    )


def _source_ref(source: WeeklySourceSnapshot) -> SwapReference:
    return SwapReference(
        record_id=source.source_id, version=source.version, content_digest=source.content_digest
    )


def _same(left: Any, right: Any) -> bool:
    return _canonical_content(left) == _canonical_content(right)


class _SavedInputs(_SwapModel):
    saved_plan: SavedPlanMaterial
    knowledge: KnowledgeBaseSnapshot
    original_context: RuleContext
    original_sources: WeeklySourceSnapshot
    original_candidates: tuple[CandidateRecipeFacts, ...]

    @model_validator(mode="after")
    def independent_original(self) -> Self:
        snapshot = self.saved_plan.snapshot
        if (
            self.original_sources != snapshot.original_sources
            or (self.original_context != snapshot.original_context)
            or not _same(
                [c.model_dump(mode="json") for c in self.original_candidates],
                [c.model_dump(mode="json") for c in snapshot.original_candidates],
            )
        ):
            raise ValueError("saved material differs from independently selected originals")
        _KnowledgeContextRequest(kb=self.knowledge, context=self.original_context)
        for candidate in self.original_candidates:
            _ManifestRequest(kb=self.knowledge, context=self.original_context, candidate=candidate)
        # Admission/complete definition selection only, no fact resolution/predicate calls.
        accepted_kb = build_knowledge_snapshot(
            self.knowledge, expected_digest=self.original_context.expected_kb_digest
        )
        _mandatory_checks(accepted_kb, self.original_context)
        return self


def validate_saved_plan_material(
    saved_plan: SavedPlanMaterial,
    *,
    knowledge: KnowledgeBaseSnapshot,
    original_context: RuleContext,
    original_sources: WeeklySourceSnapshot,
    original_candidates: tuple[CandidateRecipeFacts, ...],
) -> SavedPlanContractCheck:
    """Check structure and independent bindings; does not revalidate semantic truth."""
    accepted = _SavedInputs.model_validate(
        dict(
            saved_plan=saved_plan,
            knowledge=knowledge,
            original_context=original_context,
            original_sources=original_sources,
            original_candidates=original_candidates,
        )
    )
    return SavedPlanContractCheck(
        saved_plan=accepted.saved_plan.reference, slot_digests=_slot_digests(accepted.saved_plan)
    )


def _facts_projection(facts: list[dict[str, Any]], old: RuleContext, new: RuleContext) -> None:
    """The entire whitelist: exact context owner/references, never observed values."""
    for fact in facts:
        if (fact["context_id"], fact["context_version"]) == (old.context_id, old.version):
            fact["context_id"], fact["context_version"] = new.context_id, new.version
        if fact["subject_kind"] == "CONTEXT" and (fact["subject_id"], fact["subject_version"]) == (
            old.context_id,
            old.version,
        ):
            fact["subject_id"], fact["subject_version"] = new.context_id, new.version


class _SwapInputs(_SwapModel):
    request: PlannedSwapRequest
    saved_plan: SavedPlanMaterial
    locks: SavedPlanLockInventory
    permission: SwapTargetPermission
    knowledge: KnowledgeBaseSnapshot
    context: RuleContext
    sources: PlannedSwapSourceSnapshot
    bridge: PlannedSwapWorkflowBridge

    @model_validator(mode="after")
    def independent_swap_bindings(self) -> Self:
        request, saved, locks, permission = (
            self.request,
            self.saved_plan,
            self.locks,
            self.permission,
        )
        snapshot, source, context, bridge = saved.snapshot, self.sources, self.context, self.bridge
        _SavedInputs(
            saved_plan=saved,
            knowledge=self.knowledge,
            original_context=snapshot.original_context,
            original_sources=snapshot.original_sources,
            original_candidates=snapshot.original_candidates,
        )
        _KnowledgeContextRequest(kb=self.knowledge, context=context)
        if (
            request.saved_plan != saved.reference
            or locks.saved_plan != saved.reference
            or (permission.saved_plan != saved.reference or bridge.saved_plan != saved.reference)
        ):
            raise ValueError("stale/conflicting independently selected saved-plan revision")
        if (request.locks, permission.locks) != (_ref(locks), _ref(locks)) or (
            request.permission != _ref(permission)
        ):
            raise ValueError("request differs from complete independent lock/permission body")
        if (
            request.sources != _ref(source)
            or request.bridge != _ref(bridge)
            or request.context != _context_ref(context)
            or request.knowledge != _knowledge_ref(self.knowledge)
            or source.context != context
            or permission.context != _context_ref(context)
        ):
            raise ValueError("request/source/permission differs from independent context/KB/bridge")
        identities = tuple(s.identity for s in snapshot.slots)
        if (
            request.target not in identities
            or permission.target != request.target
            or (permission.profile_id, permission.profile_version)
            != (context.profile_id, context.profile_version)
        ):
            raise ValueError("permission does not authorize the exact original target/profile")
        if any(e.slot not in identities for e in locks.entries):
            raise ValueError("lock inventory contains a foreign original slot")
        if (
            bridge.original_context != _context_ref(snapshot.original_context)
            or bridge.original_source != _source_ref(snapshot.original_sources)
            or bridge.swap_context != _context_ref(context)
            or bridge.swap_source != _ref(source)
            or bridge.knowledge != _knowledge_ref(self.knowledge)
            or bridge.target_release != snapshot.target
            or request.target_release != snapshot.target
        ):
            raise ValueError("bridge differs from exact original/swap/target releases")
        old_context = snapshot.original_context
        if old_context.context_id == context.context_id:
            raise ValueError("swap evaluation requires a distinct context identity")
        expected = old_context.model_dump(mode="json", exclude={"content_digest"})
        expected.update(
            context_id=context.context_id, version=context.version, workflow="PLANNED_SWAP"
        )
        _facts_projection(expected["facts"], old_context, context)
        if not _same(expected, context.model_dump(mode="json", exclude={"content_digest"})):
            raise ValueError(
                "workflow bridge changes profile/facts/KB/policies beyond context whitelist"
            )
        old_recipes = {c.recipe_id: c for c in snapshot.original_candidates}
        new_recipes = {c.recipe_id: c for c in source.candidates}
        for candidate in source.candidates:
            _ManifestRequest(kb=self.knowledge, context=context, candidate=candidate)
        for recipe_id, original in old_recipes.items():
            counterpart = new_recipes.get(recipe_id)
            if counterpart is None:
                raise ValueError("missing independently supplied recipe projection")
            candidate_body = original.model_dump(mode="json", exclude={"content_digest"})
            if original.context_id is not None:
                candidate_body.update(
                    context_id=context.context_id, context_version=context.version
                )
            _facts_projection(candidate_body["facts"], old_context, context)
            if not _same(
                candidate_body, counterpart.model_dump(mode="json", exclude={"content_digest"})
            ):
                raise ValueError("recipe projection changes immutable semantic/source payload")
        originals = {
            o.reference.option_id: o for o in snapshot.original_sources.daily_source.options
        }
        projections = {o.reference.option_id: o for o in source.options}
        if {m.projected.model_dump_json() for m in bridge.mappings} != {
            o.reference.model_dump_json() for o in source.options
        }:
            raise ValueError(
                "bridge must cover the complete independently selected projection inventory"
            )
        covered = set()
        for mapping in bridge.mappings:
            projected = projections[mapping.projected.option_id]
            if mapping.original is None:
                if mapping.projected.option_id in originals:
                    raise ValueError("replacement origin cannot shadow an original identity")
                continue
            original = originals.get(mapping.original.option_id)
            if original is None or original.reference != mapping.original:
                raise ValueError("projection uses a foreign original option")
            covered.add(mapping.original.model_dump_json())
            expected_option = original.model_dump(mode="json")
            combo = expected_option["combination"]
            combo.update(
                context_id=context.context_id,
                context_version=context.version,
                context_digest=context.content_digest,
                content_digest=projected.combination.content_digest,
            )
            for part in combo["components"]:
                reference = _recipe_reference(new_recipes[part["recipe_snapshot"]["recipe_id"]])
                part["recipe_snapshot"] = reference.model_dump(mode="json")
                part["preparation"]["recipe_snapshot"] = reference.model_dump(mode="json")
            expected_option["reference"]["combination_digest"] = (
                projected.reference.combination_digest
            )
            ref = expected_option["reference"]
            if expected_option["suitability"] is not None:
                expected_option["suitability"]["option"] = ref
            for measurement in expected_option["measurements"]:
                measurement["option"] = ref
                measurement["components"] = combo["components"]
            if not _same(expected_option, projected.model_dump(mode="json")):
                raise ValueError(
                    "option projection changes fields outside the exact context whitelist"
                )
        if not {s.option.reference.model_dump_json() for s in snapshot.slots}.issubset(covered):
            raise ValueError("projection map omits an original locked/target option")
        return self


def build_swap_check_manifest(
    request: PlannedSwapRequest,
    *,
    saved_plan: SavedPlanMaterial,
    locks: SavedPlanLockInventory,
    permission: SwapTargetPermission,
    knowledge: KnowledgeBaseSnapshot,
    context: RuleContext,
    sources: PlannedSwapSourceSnapshot,
    bridge: PlannedSwapWorkflowBridge,
) -> ExpectedSwapCheckManifest:
    """Bind independent authority and select all definitions, never evaluate truth.

    A target lock is retained as a declared operation restriction for B1, not
    removed, overridden or translated into a computed REJECTED in Package A.
    """
    accepted = _SwapInputs.model_validate(
        dict(
            request=request,
            saved_plan=saved_plan,
            locks=locks,
            permission=permission,
            knowledge=knowledge,
            context=context,
            sources=sources,
            bridge=bridge,
        )
    )
    return ExpectedSwapCheckManifest.build(
        dict(
            request=accepted.request,
            knowledge=accepted.knowledge,
            context=accepted.context,
            locks=accepted.locks,
            permission=accepted.permission,
            original_slots=tuple(s.identity for s in accepted.saved_plan.snapshot.slots),
            required_checks=_mandatory_checks(accepted.knowledge, accepted.context),
        )
    )


def validate_swap(
    request: PlannedSwapRequest,
    replacement: MealOptionReference,
    *,
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
) -> ComputedSwapValidationResult:
    """Recheck both complete fixed plans; return a witness only after full replay.

    Pydantic admission errors are explicit structural boundary failures. This API
    does not authenticate the loader, persist plans, override locks or search.
    """
    from savora_ai.core.reasoning.swap_checks import (
        _admit,
        _binding_cost,
        _execute_phase,
        _input_digest,
        _Interrupted,
        _Meter,
        _proposed,
        _schedule,
        _verdict,
    )

    authority: dict[str, object] = dict(
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
    )
    inputs = _admit(authority)
    # One shared clock guard spans executor, checker and their boundary.
    guard = _Meter(clock, None, checker=False)

    def guarded_clock() -> float:
        guard.checkpoint()
        assert guard.previous is not None
        return guard.previous

    meter = _Meter(guarded_clock, limits.deadline, checker=False)
    checker_work = SwapWork()
    stage = "RESERVATION"
    try:
        schedule = _schedule(inputs)
        meter.start(_binding_cost(inputs))
        inputs = _admit(authority)
        meter.checkpoint()
        stage = "EXECUTION"
        original = _execute_phase(inputs, "ORIGINAL", meter)
        resulting = _execute_phase(inputs, "RESULT", meter)
        meter.start(SwapWork(full_validations=1))
        outcome, scope, reason = _verdict(inputs, original, resulting)
        certificate = ComputedSwapCertificate(
            input_digest=_input_digest(inputs),
            reservations=schedule.plan,
            original=original,
            result=resulting,
        )
        proof_bytes = len(certificate.model_dump_json(by_alias=True).encode())
        claim = dict(
            request=request,
            replacement=replacement,
            limits=limits,
            stage="COMPLETE",
            outcome=outcome,
            failure_scope=scope,
            reason=reason,
            certificate=certificate,
            resulting_plan=_proposed(inputs) if outcome is SwapOutcome.VALID else None,
            verification_complete=True,
            actual_execution=meter.work,
            actual_verification=schedule.verification,
            proof_bytes=proof_bytes,
        )
        # Check the complete wire envelope before the mandatory checker starts.
        from savora_ai.schemas.swap_proof import _SwapClaim

        parsed = _SwapClaim.model_validate(claim)
        if (
            proof_bytes > limits.max_proof_bytes
            or len(parsed.model_dump_json(by_alias=True).encode()) > limits.max_result_bytes
        ):
            raise _Interrupted("RESERVATION")
        meter.checkpoint()
        stage = "VERIFICATION"
        try:
            return ComputedSwapValidationResult.model_validate(
                claim, context={"authority": authority, "clock": guarded_clock}
            )
        except _Interrupted as error:
            checker_work = error.work
            raise
    except _Interrupted as error:
        return ComputedSwapValidationResult(
            request=request,
            replacement=replacement,
            limits=limits,
            stage=stage,
            outcome=SwapOutcome.TIMEOUT,
            reason=error.reason,
            actual_execution=meter.work,
            actual_verification=checker_work,
        )
    except ValidationError as error:
        # Source admission already succeeded. Only the exact bounded computed
        # envelope overflow is a resource stop; policy/binding errors propagate.
        if not all(
            e["msg"] == "Value error, swap structural envelope exceeds 1 MiB"
            for e in error.errors()
        ):
            raise
        return ComputedSwapValidationResult(
            request=request,
            replacement=replacement,
            limits=limits,
            stage=stage,
            outcome=SwapOutcome.TIMEOUT,
            reason="RESERVATION",
            actual_execution=meter.work,
            actual_verification=checker_work,
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
