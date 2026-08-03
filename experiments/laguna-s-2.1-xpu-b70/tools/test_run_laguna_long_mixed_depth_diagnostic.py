#!/usr/bin/env python3
"""CPU-only contract tests for the long-context mixed-depth wrapper.

These bind three things that are otherwise only checked at run time on the
device: the case list the wrapper selects, the row sequence the benchmark
builds from the real suite, and the row sequence the analyzer demands. No
service, model, or device is involved.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_laguna_long_mixed_depth as analyzer
import bench_laguna_long_context as producer


TOOLS = Path(__file__).resolve().parent
EXPERIMENT = TOOLS.parent
WRAPPER = TOOLS / "run_laguna_long_mixed_depth_diagnostic.sh"
SUITE = EXPERIMENT / "long-context-suite-v1.json"
ORACLE = (
    EXPERIMENT.parent.parent
    / "data"
    / "laguna-scheduler-alignment-repeat-oracle-20260802.json"
)


@pytest.fixture(scope="module")
def wrapper_text() -> str:
    return WRAPPER.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def suite() -> dict:
    return json.loads(SUITE.read_text(encoding="utf-8"))


def shell_scalar(text: str, name: str) -> str:
    match = re.search(rf"^readonly {re.escape(name)}=(\S+)$", text, re.MULTILINE)
    assert match is not None, f"{name} is not a readonly scalar in the wrapper"
    return match.group(1)


def shell_array(text: str, name: str) -> tuple[str, ...]:
    match = re.search(
        rf"^readonly {re.escape(name)}=\((.*?)\n\)$", text, re.MULTILINE | re.DOTALL
    )
    assert match is not None, f"{name} is not a readonly array in the wrapper"
    return tuple(match.group(1).split())


def built_rows(suite: dict, selected: tuple[str, ...]) -> list[tuple[str, str, int]]:
    """Replay the benchmark's selection, ordering, and sentinel rules."""
    wanted = set(selected)
    rows: list[tuple[str, str, int]] = []
    near_max_index = 0
    for case in suite["cases"]:
        if case["id"] not in wanted:
            continue
        rows.append((case["id"], "long", int(case["target_prompt_tokens"])))
        if int(case["target_prompt_tokens"]) == 32640:
            near_max_index += 1
            sentinel = producer.build_sentinel_case(case, near_max_index)
            rows.append(
                (sentinel["id"], "sentinel", int(sentinel["target_prompt_tokens"]))
            )
    return rows


def test_selected_cases_build_exactly_the_analyzer_row_sequence(
    wrapper_text: str, suite: dict
) -> None:
    selected = tuple(shell_scalar(wrapper_text, "cases").split(","))
    rows = built_rows(suite, selected)

    assert tuple(case_id for case_id, _, _ in rows) == analyzer.EXPECTED_ROW_IDS


def test_wrapper_oracle_precheck_matches_the_analyzer_rows(wrapper_text: str) -> None:
    assert shell_array(wrapper_text, "required_case_ids") == analyzer.EXPECTED_ROW_IDS


def test_built_row_kinds_and_lengths_satisfy_the_analyzer(
    wrapper_text: str, suite: dict
) -> None:
    selected = tuple(shell_scalar(wrapper_text, "cases").split(","))
    rows = {
        case_id: (kind, length) for case_id, kind, length in built_rows(suite, selected)
    }

    assert rows[analyzer.WARMUP_ID] == ("long", 1024)
    assert all(rows[case_id] == ("long", 32640) for case_id in analyzer.LONG_IDS)
    assert all(rows[case_id] == ("sentinel", 256) for case_id in analyzer.SENTINEL_IDS)


def test_every_selected_case_exists_in_the_suite(
    wrapper_text: str, suite: dict
) -> None:
    selected = set(shell_scalar(wrapper_text, "cases").split(","))
    suite_ids = {case["id"] for case in suite["cases"]}

    assert selected <= suite_ids


def test_analyzer_position_schema_pins_the_wrapper_to_draft_depth_eleven(
    wrapper_text: str,
) -> None:
    # The analyzer requires accepted-draft positions 0..10 to all be present,
    # and the metric exposes exactly num_speculative_tokens positions, so the
    # only depth that can satisfy it is 11 - which is the q12 profile.
    assert analyzer.EXPECTED_POSITIONS == {str(position) for position in range(11)}
    assert "LAGUNA_LONG_CANDIDATE_PROFILE=q12" in wrapper_text


def test_wrapper_pins_the_incumbent_scheduler_budget(wrapper_text: str) -> None:
    batched = int(shell_scalar(wrapper_text, "batched_tokens"))
    derived = int(shell_scalar(wrapper_text, "derived_scheduled_tokens"))

    # Parallel drafting reserves depth-1 slots per sequence at max_num_seqs=1.
    assert batched - (11 - 1) == derived == 8182
    assert "LAGUNA_MAX_NUM_SCHEDULED_TOKENS=auto" in wrapper_text


def test_wrapper_declares_itself_unscored(wrapper_text: str) -> None:
    assert "scored_measurement=false" in wrapper_text
    assert "promotable=false" in wrapper_text
    assert "125.4619731637751" in wrapper_text


@pytest.mark.skipif(not ORACLE.is_file(), reason="frozen repeat oracle is absent")
def test_repo_repeat_oracle_covers_every_required_row() -> None:
    payload = json.loads(ORACLE.read_text(encoding="utf-8"))
    covered = [row["case_id"] for row in payload["rows"]]

    for case_id in analyzer.EXPECTED_ROW_IDS:
        assert covered.count(case_id) == 1
