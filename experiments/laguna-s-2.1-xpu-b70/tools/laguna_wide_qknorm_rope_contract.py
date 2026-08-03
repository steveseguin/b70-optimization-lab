#!/usr/bin/env python3
"""Pure incumbent-scheduler contract for the Laguna wide-prefill gate."""

from __future__ import annotations


NATIVE_OP = "laguna_incumbent_wide_prefill_qk_norm_rope_out"
REQUIRED_ROWS = (1024, 4096, 8094, 8182)
SCHEDULE_STARTS = (0, 8182, 16364, 24546)
CHUNK_MULTIPLICITY = {
    1024: 0,
    4096: 0,
    8094: 1,
    8182: 3,
}
PROMPT_TOKENS = 32640


def position_starts(rows: int) -> tuple[int, ...]:
    if rows not in REQUIRED_ROWS:
        raise ValueError(f"rows must be one of {REQUIRED_ROWS}")
    return tuple(start for start in SCHEDULE_STARTS if start + rows <= PROMPT_TOKENS)


def projection_contribution(rows: int, cycle_saving_ms: float) -> dict[str, object]:
    if rows not in CHUNK_MULTIPLICITY:
        raise ValueError(f"rows must be one of {REQUIRED_ROWS}")
    multiplicity = CHUNK_MULTIPLICITY[rows]
    return {
        "chunk_multiplicity": multiplicity,
        "saving_ms": multiplicity * cycle_saving_ms,
        "schedule": "8182 + 8182 + 8182 + 8094 = 32640",
    }
