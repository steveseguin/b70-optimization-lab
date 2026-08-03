#!/usr/bin/env python3
"""CPU-only tests for the Laguna accuracy dataset adapters and scorers.

No network, no model, no device. The one test that touches a real file reads the
AngelSlim GSM8K sample already on this host, and skips cleanly if it is absent.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_laguna_datasets as datasets

ANGELSLIM_GSM8K = Path("/home/steve/src/AngelSlim/dataset/gsm8k/question.jsonl")
ANGELSLIM_HUMANEVAL = Path("/home/steve/src/AngelSlim/dataset/humaneval/question.jsonl")


def write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# canonicalization and revision binding
# ---------------------------------------------------------------------------


def test_canonical_text_normalizes_line_endings_and_unicode() -> None:
    assert datasets.canonical_text("a\r\nb\rc") == "a\nb\nc"
    # NFD "e" + combining acute must fold to the NFC single code point.
    assert datasets.canonical_text("é") == "é"


def test_prompt_template_hashes_cover_every_template() -> None:
    assert set(datasets.PROMPT_TEMPLATE_SHA256) == set(datasets.PROMPT_TEMPLATES)
    for name, text in datasets.PROMPT_TEMPLATES.items():
        assert datasets.PROMPT_TEMPLATE_SHA256[name] == datasets.canonical_sha256(text)


def test_scorer_revision_is_the_hash_of_this_modules_file() -> None:
    expected = datasets.sha256_bytes(Path(datasets.__file__).resolve().read_bytes())
    assert datasets.scorer_revision_sha256() == expected


def test_registry_report_flags_which_datasets_are_actually_present() -> None:
    report = datasets.registry_report()
    assert report["schema"] == datasets.SCHEMA
    entries = report["datasets"]
    # Every remote dataset must carry a provisioning instruction and must not
    # claim to be present.
    for name in ("openai_humaneval", "mbpp_sanitized", "mmlu_multiple_choice"):
        assert entries[name]["present_on_this_host"] is False
        assert entries[name]["provisioning"]
        assert entries[name]["local_bytes"] is None


def test_code_exec_scorer_is_not_reachable_by_importing_this_module() -> None:
    assert datasets.CODE_EXEC_SCORER not in datasets.SCORERS


# ---------------------------------------------------------------------------
# GSM8K extraction
# ---------------------------------------------------------------------------


def test_reference_final_number_reads_the_last_hash_marker() -> None:
    assert datasets.extract_reference_final_number("work\n#### 109") == "109"
    assert datasets.extract_reference_final_number("#### 1\nmore\n#### 42") == "42"
    assert datasets.extract_reference_final_number("no marker 7") is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("blah\n#### 109", "109"),
        ("#### 5\nand then\n#### 7", "7"),
        ("The answer is 42.", "42"),
        ("Answer: 1,234", "1234"),
        ("first 3 then 4 then 9", "9"),
        ("-17 is it", "-17"),
        ("value 2.50", "2.5"),
        ("no digits at all", None),
    ],
)
def test_extract_final_number_follows_the_frozen_rule_order(
    text: str, expected: str | None
) -> None:
    assert datasets.extract_final_number(text) == expected


def test_hash_marker_wins_over_a_later_answer_phrase() -> None:
    # Rule 1 outranks rule 2 even when the answer phrase appears afterwards.
    assert datasets.extract_final_number("#### 11\nthe answer is 99") == "11"


# ---------------------------------------------------------------------------
# multiple-choice extraction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Reasoning...\nAnswer: C", "C"),
        ("Answer: A\nAnswer: D", "D"),
        ("I pick B", "B"),
        ("APPLE BANANA", None),
        ("nothing here", None),
    ],
)
def test_extract_choice_letter(text: str, expected: str | None) -> None:
    assert datasets.extract_choice_letter(text) == expected


def test_choice_letter_ignores_letters_embedded_in_words() -> None:
    # The D of "Dog" is not a standalone letter and must not be read as an
    # answer. The leading "A" is standalone, so the fallback rule returns it --
    # which is exactly why the prompt demands an explicit "Answer: X" line and
    # why rule 1 outranks this fallback.
    assert datasets.extract_choice_letter("A cat ate a Dog") == "A"
    assert datasets.extract_choice_letter("Dogs and Cats") is None


# ---------------------------------------------------------------------------
# code extraction
# ---------------------------------------------------------------------------


def test_code_block_prefers_the_last_block_defining_the_entry_point() -> None:
    text = (
        "First an idea:\n```python\ndef other():\n    pass\n```\n"
        "Now the answer:\n```python\ndef solve(x):\n    return x\n```\n"
        "Usage:\n```python\nsolve(1)\n```\n"
    )
    assert datasets.extract_code_block(text, "solve") == "def solve(x):\n    return x"


def test_code_block_falls_back_to_the_first_block_then_to_raw_text() -> None:
    text = "```python\ndef nope():\n    pass\n```\n"
    assert datasets.extract_code_block(text, "solve") == "def nope():\n    pass"
    assert datasets.extract_code_block("def solve(): return 1", "solve") == (
        "def solve(): return 1"
    )
    assert datasets.extract_code_block("   \n  ", "solve") is None


def test_code_block_accepts_an_unterminated_fence_from_a_truncated_response() -> None:
    text = "```python\ndef solve(x):\n    return x"
    assert datasets.extract_code_block(text, "solve") == "def solve(x):\n    return x"


def test_build_code_program_handles_standalone_and_body_only_completions() -> None:
    item = datasets.EvalItem(
        item_id="d:1",
        dataset="openai_humaneval",
        scorer=datasets.CODE_EXEC_SCORER,
        prompt_text="",
        expected={
            "prompt": "def solve(x):\n",
            "test": "def check(f):\n    assert f(1) == 1\n",
            "entry_point": "solve",
        },
        row_id="1",
        max_output_tokens=64,
    )
    standalone = datasets.build_code_program(
        item, "```python\ndef solve(x):\n    return x\n```"
    )
    assert standalone is not None
    assert "def solve(x):" in standalone
    assert standalone.rstrip().endswith("check(solve)")

    body_only = datasets.build_code_program(item, "```python\n    return x\n```")
    assert body_only is not None
    assert body_only.startswith("def solve(x):\n    return x")

    assert datasets.build_code_program(item, "```python\n```") is None
    # A non-indented completion that never defines the entry point is not a body
    # and must not be silently glued onto the prompt.
    assert datasets.build_code_program(item, "```python\nreturn x\n```") is None


# ---------------------------------------------------------------------------
# loader: refusals
# ---------------------------------------------------------------------------


def test_unknown_dataset_is_refused(tmp_path: Path) -> None:
    with pytest.raises(datasets.DatasetUnavailable) as error:
        datasets.load_items("not_a_dataset", tmp_path / "x.jsonl")
    assert error.value.as_refusal()["kind"] == "dataset_unavailable"


def test_absent_file_is_refused_with_provisioning_instructions(tmp_path: Path) -> None:
    with pytest.raises(datasets.DatasetUnavailable) as error:
        datasets.load_items("openai_humaneval", tmp_path / "missing.jsonl")
    refusal = error.value.as_refusal()
    assert "absent" in refusal["reason"]
    assert "task_id" in refusal["provisioning"]


def test_sha256_mismatch_is_refused_not_warned(tmp_path: Path) -> None:
    path = write_jsonl(
        tmp_path / "mmlu.jsonl",
        [
            {
                "subject": "s",
                "question": "q",
                "choices": ["a", "b", "c", "d"],
                "answer": 0,
            }
        ],
    )
    with pytest.raises(datasets.DatasetUnavailable) as error:
        datasets.load_items("mmlu_multiple_choice", path, expected_sha256="0" * 64)
    assert "SHA-256" in error.value.reason
    assert "do not edit the contract" in error.value.provisioning


def test_row_count_drift_is_refused(tmp_path: Path) -> None:
    path = write_jsonl(
        tmp_path / "gsm8k.jsonl",
        [{"question_id": 0, "turns": ["q"], "reference": ["x\n#### 1"]}],
    )
    with pytest.raises(datasets.DatasetUnavailable) as error:
        datasets.load_items("angelslim_gsm8k", path)
    assert "registry declares" in error.value.reason


def test_limit_above_available_items_is_refused(tmp_path: Path) -> None:
    rows = [
        {"subject": "s", "question": f"q{index}", "choices": list("abcd"), "answer": 0}
        for index in range(3)
    ]
    path = write_jsonl(tmp_path / "mmlu.jsonl", rows)
    with pytest.raises(datasets.DatasetUnavailable) as error:
        datasets.load_items("mmlu_multiple_choice", path, limit=10)
    assert "exceeds" in error.value.reason


def test_duplicate_item_ids_are_refused(tmp_path: Path) -> None:
    rows = [
        {"task_id": "T/1", "prompt": "p", "test": "t", "entry_point": "f"},
        {"task_id": "T/1", "prompt": "p", "test": "t", "entry_point": "f"},
    ]
    path = write_jsonl(tmp_path / "he.jsonl", rows)
    with pytest.raises(datasets.DatasetUnavailable) as error:
        datasets.load_items("openai_humaneval", path)
    assert "duplicate item ids" in error.value.reason


def test_multi_turn_rows_are_refused(tmp_path: Path) -> None:
    path = write_jsonl(
        tmp_path / "gsm8k.jsonl",
        [{"question_id": 0, "turns": ["a", "b"], "reference": ["#### 1"]}],
    )
    with pytest.raises(datasets.DatasetUnavailable) as error:
        datasets.load_items("angelslim_gsm8k", path)
    assert "one turn" in error.value.reason


def test_gsm8k_reference_without_a_final_answer_is_refused(tmp_path: Path) -> None:
    path = write_jsonl(
        tmp_path / "gsm8k.jsonl",
        [{"question_id": 0, "turns": ["q"], "reference": ["no marker"]}],
    )
    with pytest.raises(datasets.DatasetUnavailable) as error:
        datasets.load_items("angelslim_gsm8k", path)
    assert "#### <number>" in error.value.reason


# ---------------------------------------------------------------------------
# loader: adapters
# ---------------------------------------------------------------------------


def test_humaneval_adapter_refuses_a_file_without_tests(tmp_path: Path) -> None:
    """The decisive constraint on the locally available HumanEval sample.

    The AngelSlim file carries prompts and reference solutions but no ``test``
    and no ``entry_point``, so pass@1 cannot be computed from it. The adapter
    must say so rather than invent a similarity score.
    """

    rows = [
        {"task_id": "HumanEval/0", "prompt": "def f():\n", "reference": ["    pass"]}
    ]
    path = write_jsonl(tmp_path / "he.jsonl", rows)
    with pytest.raises(datasets.DatasetUnavailable) as error:
        datasets.load_items("openai_humaneval", path)
    assert "test" in error.value.reason and "entry_point" in error.value.reason


def test_mmlu_adapter_accepts_integer_and_letter_answers(tmp_path: Path) -> None:
    rows = [
        {"subject": "s", "question": "q0", "choices": list("abcd"), "answer": 2},
        {"subject": "s", "question": "q1", "choices": list("abcd"), "answer": "d"},
    ]
    path = write_jsonl(tmp_path / "mmlu.jsonl", rows)
    items, provenance = datasets.load_items("mmlu_multiple_choice", path)
    assert [item.expected["letter"] for item in items] == ["C", "D"]
    assert "A. a" in items[0].prompt_text and "D. d" in items[0].prompt_text
    assert provenance["scorer"] == "multiple_choice_letter"


def test_mmlu_adapter_refuses_a_malformed_answer(tmp_path: Path) -> None:
    rows = [{"subject": "s", "question": "q", "choices": list("abcd"), "answer": 9}]
    path = write_jsonl(tmp_path / "mmlu.jsonl", rows)
    with pytest.raises(datasets.DatasetUnavailable):
        datasets.load_items("mmlu_multiple_choice", path)


def test_mbpp_adapter_builds_prompt_and_joins_the_test_list(tmp_path: Path) -> None:
    rows = [
        {
            "task_id": 11,
            "text": "Write a function.",
            "test_list": ["assert f(1) == 1", "assert f(2) == 2"],
        }
    ]
    path = write_jsonl(tmp_path / "mbpp.jsonl", rows)
    items, _ = datasets.load_items("mbpp_sanitized", path)
    assert items[0].item_id == "mbpp_sanitized:11"
    assert "assert f(1) == 1" in items[0].prompt_text
    assert items[0].expected["test"] == "assert f(1) == 1\nassert f(2) == 2"
    assert items[0].expected["entry_point"] is None


def test_agent_format_suite_loads_and_refuses_empty_expectations(
    tmp_path: Path,
) -> None:
    good = tmp_path / "agent.json"
    good.write_text(
        json.dumps(
            {
                "suite_id": "laguna-agent-format-v1",
                "version": 1,
                "cases": [
                    {
                        "id": "edit-plan",
                        "prompt": "Return JSON.",
                        "max_output_tokens": 128,
                        "expected_fields": {"action": "edit", "path": "a.py"},
                    }
                ],
            }
        )
    )
    items, provenance = datasets.load_items("laguna_agent_format", good)
    assert items[0].item_id == "laguna_agent_format:edit-plan"
    assert items[0].max_output_tokens == 128
    assert provenance["scorer"] == "json_fields"

    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps(
            {
                "suite_id": "s",
                "version": 1,
                "cases": [{"id": "x", "prompt": "p", "expected_fields": {}}],
            }
        )
    )
    with pytest.raises(datasets.DatasetUnavailable):
        datasets.load_items("laguna_agent_format", bad)


# ---------------------------------------------------------------------------
# loader: the real local file
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not ANGELSLIM_GSM8K.is_file(), reason="AngelSlim GSM8K sample is not on this host"
)
def test_local_gsm8k_sample_loads_completely_and_hashes_stably() -> None:
    items, provenance = datasets.load_items("angelslim_gsm8k", ANGELSLIM_GSM8K)
    assert len(items) == 80
    assert provenance["file_bytes"] == 48188
    assert provenance["items_available"] == 80
    assert all(item.expected["final_answer"] for item in items)
    assert len({item.item_id for item in items}) == 80
    # The frozen prompt must actually ask for the format the scorer reads.
    assert "four hash characters" in items[0].prompt_text
    # Loading twice must give byte-identical provenance.
    _, again = datasets.load_items("angelslim_gsm8k", ANGELSLIM_GSM8K)
    assert provenance == again


@pytest.mark.skipif(
    not ANGELSLIM_HUMANEVAL.is_file(),
    reason="AngelSlim HumanEval sample is not on this host",
)
def test_local_humaneval_sample_is_loadable_but_cannot_be_scored() -> None:
    items, provenance = datasets.load_items(
        "angelslim_humaneval_prompts", ANGELSLIM_HUMANEVAL
    )
    assert len(items) == 80
    assert provenance["scorer"] == "reference_unscoreable"
    result = datasets.SCORERS["reference_unscoreable"](items[0], "anything at all")
    assert result["correct"] is None
    assert result["scoreable"] is False
    assert "no executable tests" in result["reason"]


# ---------------------------------------------------------------------------
# scorers
# ---------------------------------------------------------------------------


def make_item(scorer: str, expected: dict) -> datasets.EvalItem:
    return datasets.EvalItem(
        item_id="d:1",
        dataset="d",
        scorer=scorer,
        prompt_text="p",
        expected=expected,
        row_id="1",
        max_output_tokens=64,
    )


def test_gsm8k_scorer_marks_missing_answers_unscoreable_not_correct() -> None:
    item = make_item("gsm8k_final_number", {"final_answer": "109"})
    assert datasets.score_gsm8k_final_number(item, "#### 109")["correct"] is True
    wrong = datasets.score_gsm8k_final_number(item, "#### 110")
    assert wrong["correct"] is False and wrong["scoreable"] is True
    empty = datasets.score_gsm8k_final_number(item, "I do not know")
    assert empty["correct"] is False and empty["scoreable"] is False


def test_gsm8k_scorer_normalizes_commas_and_trailing_zeros() -> None:
    item = make_item("gsm8k_final_number", {"final_answer": "1234"})
    assert datasets.score_gsm8k_final_number(item, "#### 1,234")["correct"] is True


def test_multiple_choice_scorer() -> None:
    item = make_item("multiple_choice_letter", {"letter": "B"})
    assert datasets.score_multiple_choice_letter(item, "Answer: B")["correct"] is True
    assert datasets.score_multiple_choice_letter(item, "Answer: C")["correct"] is False
    missing = datasets.score_multiple_choice_letter(item, "no idea")
    assert missing["scoreable"] is False


def test_json_fields_scorer_requires_every_declared_field() -> None:
    item = make_item("json_fields", {"fields": {"action": "edit", "path": "a.py"}})
    good = datasets.score_json_fields(item, '{"action": "edit", "path": "a.py"}')
    assert good["correct"] is True
    partial = datasets.score_json_fields(item, '{"action": "edit", "path": "b.py"}')
    assert partial["correct"] is False
    assert partial["field_pass"] == {"action": True, "path": False}
    broken = datasets.score_json_fields(item, "not json")
    assert broken["correct"] is False and broken["scoreable"] is False


def test_json_fields_scorer_tolerates_trailing_prose_after_the_object() -> None:
    item = make_item("json_fields", {"fields": {"action": "edit"}})
    result = datasets.score_json_fields(item, '{"action": "edit"} then chatter')
    assert result["correct"] is True
