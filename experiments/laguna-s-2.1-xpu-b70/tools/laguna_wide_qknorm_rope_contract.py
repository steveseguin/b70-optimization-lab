#!/usr/bin/env python3
"""Pure incumbent-scheduler contract for the Laguna wide-prefill gate."""

from __future__ import annotations


NATIVE_OP = "laguna_incumbent_wide_prefill_qk_norm_rope_out"
WG4_NATIVE_OP = "laguna_incumbent_wide_prefill_qk_norm_rope_wg4_out"
REQUIRED_ROWS = (1024, 4096, 8094, 8182)
# 8,182 x 14 is not a multiple of eight, so the long rows cannot reuse the
# short-row work-group geometry. Two and four both divide every registered
# row/head product, and the choice only repacks heads into work-groups: each
# head keeps its own 16-lane reduction, so both geometries must produce
# identical bits and differ only in occupancy. The component matrix measures
# both and the aggregator promotes whichever is faster.
GEOMETRIES = ("wg2", "wg4")
DEFAULT_GEOMETRY = "wg2"
LONG_ROWS = (8094, 8182)
SCHEDULE_STARTS = (0, 8182, 16364, 24546)
CHUNK_MULTIPLICITY = {
    1024: 0,
    4096: 0,
    8094: 1,
    8182: 3,
}
PROMPT_TOKENS = 32640


def native_op_for_geometry(geometry: str) -> str:
    if geometry not in GEOMETRIES:
        raise ValueError(f"geometry must be one of {GEOMETRIES}")
    return NATIVE_OP if geometry == DEFAULT_GEOMETRY else WG4_NATIVE_OP


def geometries_for_rows(rows: int) -> tuple[str, ...]:
    """Geometries the matrix must cover for a registered row count.

    The short rows keep eight heads per work-group in both variants, so
    measuring them twice would compare a shape against itself.
    """
    if rows not in REQUIRED_ROWS:
        raise ValueError(f"rows must be one of {REQUIRED_ROWS}")
    return GEOMETRIES if rows in LONG_ROWS else (DEFAULT_GEOMETRY,)


def required_matrix(ranks) -> set[tuple[int, int, str]]:
    return {
        (rank, rows, geometry)
        for rank in ranks
        for rows in REQUIRED_ROWS
        for geometry in geometries_for_rows(rows)
    }


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
