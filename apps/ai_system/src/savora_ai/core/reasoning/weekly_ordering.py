"""Execution-only deterministic ordering over admitted ORIGINAL domains.

The proof checker reconstructs these choices separately. No eligibility filtering,
domain reduction, dynamic MRV, degree or ranker is an ordering input.
"""

from savora_ai.schemas.weekly_search_v2 import WeeklyStrategyPolicyV2 as Policy

ORDERED_POLICIES = frozenset(
    (
        Policy.REVERSE_VALUES,
        Policy.STATIC_MRV,
        Policy.STATIC_MRV_FORWARD_CHECKING,
        Policy.STATIC_MRV_INCREMENTAL,
        Policy.STATIC_MRV_INCREMENTAL_FORWARD_CHECKING,
    )
)


def _ordered_domains(domains, strategy):
    if strategy.variable_order == "STATIC_MRV_ORIGINAL_DOMAINS":
        return tuple(sorted(domains, key=lambda d: (len(d.options), d.slot.canonical_index)))
    return domains


def _ordering_cost(domains):
    # One visit per original variable and option; a fixed semantic preparation
    # charge, not CPU comparisons. The verifier reserves matching work.
    return dict(heuristic_evaluations=21 + sum(len(d.options) for d in domains))


def _day_completed(domains, path):
    day = domains[len(path) - 1].slot.day.day_index
    return sum(d.slot.day.day_index == day for d in domains[: len(path)]) == 3
