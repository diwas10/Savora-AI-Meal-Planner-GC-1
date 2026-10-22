"""Private request-local execution arithmetic, never proof authority or a DTO.

Each push publishes an immutable snapshot. A LIFO token restores the exact previous
object; no subtractive or partly reverted aggregate can leak into a sibling. At most
21 frames exist. Measurements and unique recipe IDs bind exact original options.
The independent checker neither constructs nor reads this state.
"""

from dataclasses import dataclass
from types import MappingProxyType

from savora_ai.core.reasoning.week_checks import _WeekProgram
from savora_ai.schemas.daily import MealOptionReference
from savora_ai.schemas.daily_solver import DailyOptionDecision
from savora_ai.schemas.filtering import _DAY_MAX_TOTAL, _WEEK_MAX_TOTAL
from savora_ai.schemas.reasoning import RuleStatus
from savora_ai.schemas.weekly_search_v2 import WeeklyOriginalDomainV2, WeeklySlotIdentityV2


@dataclass(frozen=True, slots=True)
class _Quantity:
    known_total: int = 0
    unknown: int = 0
    selected: int = 0

    def add(self, value: int | None, maximum: int) -> "_Quantity":
        total = self.known_total + (value if value is not None else 0)
        if not 0 <= total <= maximum:
            raise ValueError("incremental quantity exceeds admitted representation")
        return _Quantity(total, self.unknown + int(value is None), self.selected + 1)

    def observation(self, required: int) -> tuple[int | None, bool]:
        complete = self.selected == required and self.unknown == 0
        return (self.known_total if complete else None), complete


@dataclass(frozen=True, slots=True)
class _Snapshot:
    choices: tuple[tuple[int, MealOptionReference], ...] = ()
    days: tuple[_Quantity, ...] = (_Quantity(),) * 7
    week: _Quantity = _Quantity()
    recipe_counts: tuple[tuple[str, int], ...] = ()
    unknown_recipe_slots: int = 0


@dataclass(frozen=True, slots=True)
class _Frame:
    before: _Snapshot
    after: _Snapshot


@dataclass(frozen=True, slots=True)
class _Contribution:
    value: int | None
    recipes: tuple[str, ...]
    recipe_identity_complete: bool


class _IncrementalState:
    """Accept only admitted original material; no external cached aggregate input."""

    def __init__(
        self,
        program: _WeekProgram,
        domains: tuple[WeeklyOriginalDomainV2, ...],
        decisions: dict[str, DailyOptionDecision],
    ) -> None:
        self._domains = domains
        required = {ref.option_id: ref for domain in domains for ref in domain.options}
        contributions: dict[MealOptionReference, _Contribution] = {}
        for option in program.manifest.request.source.daily_source.options:
            ref = option.reference
            if required.get(ref.option_id) != ref:
                continue
            records = option.measurements
            value = records[0].value if records and records[0].complete else None
            if value is not None and (
                type(value) is not int or not 0 <= value <= _DAY_MAX_TOTAL // 3
            ):
                raise ValueError("incremental measurement is outside the admitted integer range")
            decision = decisions[ref.option_id]
            if decision.option != ref:
                raise ValueError("incremental preparation differs from exact source configuration")
            contributions[ref] = _Contribution(
                value,
                tuple(sorted({p.recipe_snapshot.recipe_id for p in option.combination.components})),
                all(
                    p.status is RuleStatus.PASS
                    for p in decision.combination.prerequisites
                    if p.name
                    in ("CANDIDATE_MEMBERSHIP", "COMPOSITION_COMPLETENESS", "SOURCE_AUTHORITY")
                ),
            )
        if len(contributions) != len(required):
            raise ValueError("incremental state lacks original source options")
        self._contributions = MappingProxyType(contributions)
        self._root = _Snapshot()
        self._current = self._root
        self._frames: list[_Frame] = []

    def snapshot(self) -> _Snapshot:
        return self._current

    def push(self, slot: WeeklySlotIdentityV2, ref: MealOptionReference) -> _Frame:
        index = slot.canonical_index
        if (
            type(index) is not int
            or not 0 <= index < 21
            or slot != self._domains[index].slot
            or ref not in self._domains[index].options
        ):
            raise ValueError(
                "incremental selection differs from original slot/domain/configuration"
            )
        before = self._current
        if len(self._frames) >= 21 or any(i == index for i, _ in before.choices):
            raise ValueError("incremental slot is already selected")
        contribution = self._contributions[ref]
        days = list(before.days)
        days[index // 3] = days[index // 3].add(contribution.value, _DAY_MAX_TOTAL)
        counts = dict(before.recipe_counts)
        for recipe in contribution.recipes:
            counts[recipe] = counts.get(recipe, 0) + 1
            if counts[recipe] > 21:
                raise ValueError("incremental recipe count exceeds slot capacity")
        after = _Snapshot(
            tuple(sorted((*before.choices, (index, ref)))),
            tuple(days),
            before.week.add(contribution.value, _WEEK_MAX_TOTAL),
            tuple(sorted(counts.items())),
            before.unknown_recipe_slots + int(not contribution.recipe_identity_complete),
        )
        frame = _Frame(before, after)
        self._frames.append(frame)
        self._current = after
        return frame

    def pop(self, frame: _Frame) -> None:
        if not self._frames or self._frames[-1] is not frame or self._current is not frame.after:
            raise ValueError("incremental rollback token/state differs from active frame")
        self._current = frame.before
        self._frames.pop()

    def bind_path(self, domains: tuple[WeeklyOriginalDomainV2, ...], path: tuple[int, ...]) -> None:
        if (
            len(domains) != 21
            or {d.slot.canonical_index for d in domains} != set(range(21))
            or any(d is not self._domains[d.slot.canonical_index] for d in domains)
            or self._current.choices
            != tuple(
                sorted(
                    (domains[i].slot.canonical_index, domains[i].options[position])
                    for i, position in enumerate(path)
                )
            )
        ):
            raise ValueError("incremental state differs from active original assignment")

    def day_values(self, index: int) -> tuple[int | None, bool]:
        return self._current.days[index].observation(3)

    def week_values(self) -> tuple[int | None, bool, int | None, bool]:
        current = self._current
        total, complete = current.week.observation(21)
        count_complete = current.week.selected == 21 and current.unknown_recipe_slots == 0
        maximum = (
            max((count for _, count in current.recipe_counts), default=0)
            if count_complete
            else None
        )
        return total, complete, maximum, count_complete

    def assert_empty(self) -> None:
        if self._frames or self._current is not self._root:
            raise ValueError("incremental rollback did not restore the exact root state")
