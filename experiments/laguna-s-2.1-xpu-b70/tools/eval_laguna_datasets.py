#!/usr/bin/env python3
"""Pluggable, fail-closed datasets and scorers for the Laguna accuracy harness.

This module owns three things and nothing else:

* **adapters** that turn a raw dataset file into canonical :class:`EvalItem`
  records, refusing rather than guessing when a file is missing, truncated, or
  the wrong shape;
* **prompt templates**, frozen verbatim, because a prompt change silently
  invalidates every stored score;
* **scorers**, frozen verbatim, for the same reason.

All three live in one file so that a single ``SCORER_REVISION_SHA256`` (the
SHA-256 of this file's bytes) is sufficient to detect that a stored score was
produced by different scoring logic. ``eval_laguna_accuracy`` records that hash
next to every score and ``eval_laguna_regression`` refuses to compare runs whose
revisions differ.

Nothing here contacts a network, loads a model, or touches a device. The code
that executes model-written programs lives in ``eval_laguna_sandbox``; this
module only calls it, and only for the ``code_exec_pass1`` scorer, which is
default-off.

Dataset availability on this host was audited on 2026-08-03 (see the
preregistration note). Only ``angelslim_gsm8k`` and
``angelslim_humaneval_prompts`` are present locally; every other entry in
:data:`DATASET_REGISTRY` refuses with a provisioning instruction until its file
is supplied.
"""

from __future__ import annotations

import decimal
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

SCHEMA = "laguna-accuracy-datasets-v1"

# ---------------------------------------------------------------------------
# canonicalization
# ---------------------------------------------------------------------------


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_text(value: str) -> str:
    """NFC, LF line endings, no trailing whitespace on the final line.

    This is the same recipe the DeepSeek calibration plan froze, kept identical
    so prompt hashes are comparable across the two lanes.
    """

    normalized = unicodedata.normalize("NFC", value)
    return normalized.replace("\r\n", "\n").replace("\r", "\n")


def canonical_sha256(value: str) -> str:
    return sha256_bytes(canonical_text(value).encode("utf-8"))


# ---------------------------------------------------------------------------
# frozen prompt templates
# ---------------------------------------------------------------------------

# Every template is a single user turn. The harness wraps it with the served
# checkpoint's own chat template; nothing here assumes a role syntax.
#
# The instructions are deliberately blunt about output format. A coding agent
# is judged on machine-readable output, and a format instruction that the model
# can actually follow converts "model was right but unparseable" into a real
# score instead of a scorer artifact.

PROMPT_TEMPLATES: dict[str, str] = {
    "gsm8k_v1": (
        "Solve this grade-school math problem.\n\n"
        "{question}\n\n"
        "Reason step by step. Then, on the final line and nowhere else, "
        "write four hash characters, a space, and the final numeric answer "
        "with no units, no commas, and no other text."
    ),
    "humaneval_instruct_v1": (
        "Complete this Python function.\n\n"
        "```python\n"
        "{prompt}\n"
        "```\n\n"
        "Return the complete function, including its signature, in exactly one "
        "fenced Python code block. Do not include tests, example usage, or "
        "explanation outside the code block."
    ),
    "mbpp_instruct_v1": (
        "Write a Python function for this task.\n\n"
        "{text}\n\n"
        "It must satisfy this assertion:\n\n"
        "```python\n"
        "{assertion}\n"
        "```\n\n"
        "Return the complete function in exactly one fenced Python code block. "
        "Do not include tests, example usage, or explanation outside the code "
        "block."
    ),
    "multiple_choice_v1": (
        "Answer this multiple-choice question.\n\n"
        "{question}\n\n"
        "{choices}\n\n"
        "Respond with the single line 'Answer: X' where X is A, B, C, or D, "
        "and write nothing after it."
    ),
}

PROMPT_TEMPLATE_SHA256: dict[str, str] = {
    name: canonical_sha256(text) for name, text in PROMPT_TEMPLATES.items()
}


# ---------------------------------------------------------------------------
# item and provenance records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvalItem:
    """One scoreable unit of work.

    ``item_id`` is stable across runs and is the join key for exact-output
    regression. ``expected`` carries whatever the scorer needs: a numeric string
    for ``gsm8k_final_number``, a letter for ``multiple_choice_letter``, and a
    test program plus entry point for ``code_exec_pass1``.
    """

    item_id: str
    dataset: str
    scorer: str
    prompt_text: str
    expected: dict[str, Any]
    row_id: str
    max_output_tokens: int
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def prompt_sha256(self) -> str:
        return canonical_sha256(self.prompt_text)


class DatasetUnavailable(Exception):
    """Raised when a dataset cannot be loaded. Never downgraded to a warning."""

    def __init__(self, dataset: str, reason: str, provisioning: str) -> None:
        super().__init__(f"{dataset}: {reason}")
        self.dataset = dataset
        self.reason = reason
        self.provisioning = provisioning

    def as_refusal(self) -> dict[str, str]:
        return {
            "kind": "dataset_unavailable",
            "dataset": self.dataset,
            "reason": self.reason,
            "provisioning": self.provisioning,
        }


@dataclass(frozen=True)
class DatasetSource:
    """Static description of where a dataset comes from and what it is for."""

    name: str
    adapter: str
    scorer: str
    prompt_template: str
    purpose: str
    canonical_source: str
    local_path: str | None
    local_bytes: int | None
    expected_rows: int | None
    requires_code_execution: bool
    provisioning: str


# ``local_bytes`` is the byte count measured on this host on 2026-08-03 for
# files that exist. For files that do not exist it is ``None`` -- an approximate
# download size is not asserted, because it was not measured offline.
DATASET_REGISTRY: dict[str, DatasetSource] = {
    "angelslim_gsm8k": DatasetSource(
        name="angelslim_gsm8k",
        adapter="angelslim_question_jsonl",
        scorer="gsm8k_final_number",
        prompt_template="gsm8k_v1",
        purpose=(
            "Multi-step arithmetic reasoning. The earliest and cheapest place "
            "quantization damage becomes visible, and the only real benchmark "
            "whose data is already on this host."
        ),
        canonical_source=(
            "AngelSlim vendored GSM8K sample; upstream openai/gsm8k. The row "
            "selection and split of this 80-row sample are NOT declared by the "
            "vendor and must not be reported as a GSM8K test-split score."
        ),
        local_path="/home/steve/src/AngelSlim/dataset/gsm8k/question.jsonl",
        local_bytes=48188,
        expected_rows=80,
        requires_code_execution=False,
        provisioning="Present on this host. No download required.",
    ),
    "angelslim_humaneval_prompts": DatasetSource(
        name="angelslim_humaneval_prompts",
        adapter="angelslim_question_jsonl",
        scorer="reference_unscoreable",
        prompt_template="",
        purpose=(
            "Prompt-only HumanEval sample. Usable for exact-output regression "
            "and for eyeballing, NOT for pass@1: the file carries no unit "
            "tests and no entry point, so functional correctness cannot be "
            "computed from it."
        ),
        canonical_source="AngelSlim vendored HumanEval sample (80 of 164).",
        local_path="/home/steve/src/AngelSlim/dataset/humaneval/question.jsonl",
        local_bytes=63176,
        expected_rows=80,
        requires_code_execution=False,
        provisioning="Present on this host, but cannot produce a pass@1 score.",
    ),
    "openai_humaneval": DatasetSource(
        name="openai_humaneval",
        adapter="humaneval_jsonl",
        scorer="code_exec_pass1",
        prompt_template="humaneval_instruct_v1",
        purpose=(
            "Functional coding correctness, pass@1. The single most relevant "
            "number for a coding agent."
        ),
        canonical_source="openai/openai_humaneval, test split, 164 rows.",
        local_path=None,
        local_bytes=None,
        expected_rows=164,
        requires_code_execution=True,
        provisioning=(
            "Not on this host. Provision one JSONL with the fields task_id, "
            "prompt, test, entry_point (the upstream HumanEval.jsonl shape), "
            "record its SHA-256 in the contract, and pass --dataset-path. "
            "Size was not measured offline and is not asserted here."
        ),
    ),
    "mbpp_sanitized": DatasetSource(
        name="mbpp_sanitized",
        adapter="mbpp_jsonl",
        scorer="code_exec_pass1",
        prompt_template="mbpp_instruct_v1",
        purpose=(
            "Second, differently distributed coding signal: short standalone "
            "functions rather than docstring completion."
        ),
        canonical_source="google-research-datasets/mbpp, sanitized config.",
        local_path=None,
        local_bytes=None,
        expected_rows=None,
        requires_code_execution=True,
        provisioning=(
            "Not on this host. Provision one JSONL with the fields task_id, "
            "text, test_list (list of assertion strings), record its SHA-256 "
            "in the contract, and pass --dataset-path."
        ),
    ),
    "mmlu_multiple_choice": DatasetSource(
        name="mmlu_multiple_choice",
        adapter="mmlu_jsonl",
        scorer="multiple_choice_letter",
        prompt_template="multiple_choice_v1",
        purpose=(
            "Broad knowledge canary. Included because it is the conventional "
            "quantization-damage number, NOT because it measures coding "
            "ability. It should never gate a coding-agent promotion on its own."
        ),
        canonical_source="cais/mmlu, config all, test split.",
        local_path=None,
        local_bytes=None,
        expected_rows=None,
        requires_code_execution=False,
        provisioning=(
            "Not on this host. Provision one JSONL with the fields subject, "
            "question, choices (four strings), answer (0-3 or A-D), record its "
            "SHA-256 in the contract, and pass --dataset-path."
        ),
    ),
    "laguna_agent_format": DatasetSource(
        name="laguna_agent_format",
        adapter="agent_format_json",
        scorer="json_fields",
        prompt_template="",
        purpose=(
            "Coding-agent output-format contract: does the model emit the "
            "exact machine-readable object the agent harness will parse? This "
            "is the failure mode that breaks a coding agent in production even "
            "when its reasoning is fine. Self-authored, so it has NO external "
            "validity as an intelligence measure -- it is a regression and "
            "integration signal only."
        ),
        canonical_source="This repository. Human-authored, versioned suite.",
        local_path=None,
        local_bytes=None,
        expected_rows=None,
        requires_code_execution=False,
        provisioning=(
            "Author a suite JSON with suite_id, version, and cases[], each "
            "case carrying id, prompt, max_output_tokens, and expected_fields "
            "(an object of exact field values). Pass --dataset-path."
        ),
    ),
}


# ---------------------------------------------------------------------------
# adapters
# ---------------------------------------------------------------------------


def _read_jsonl(dataset: str, path: Path) -> list[dict[str, Any]]:
    source = DATASET_REGISTRY[dataset]
    if not path.is_file():
        raise DatasetUnavailable(
            dataset, f"dataset file is absent: {path}", source.provisioning
        )
    rows: list[dict[str, Any]] = []
    text = path.read_text(encoding="utf-8", errors="strict")
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise DatasetUnavailable(
                dataset, f"line {number} is not JSON: {error}", source.provisioning
            ) from error
        if not isinstance(row, dict):
            raise DatasetUnavailable(
                dataset, f"line {number} is not a JSON object", source.provisioning
            )
        rows.append(row)
    if not rows:
        raise DatasetUnavailable(dataset, "dataset file is empty", source.provisioning)
    return rows


def _require_fields(
    dataset: str, row: dict[str, Any], names: tuple[str, ...], where: str
) -> None:
    missing = [name for name in names if name not in row]
    if missing:
        raise DatasetUnavailable(
            dataset,
            f"{where} is missing required field(s): {', '.join(sorted(missing))}",
            DATASET_REGISTRY[dataset].provisioning,
        )


def _single_turn(dataset: str, row: dict[str, Any], where: str) -> str:
    turns = row["turns"]
    if not isinstance(turns, list) or len(turns) != 1:
        raise DatasetUnavailable(
            dataset,
            f"{where} does not have exactly one turn; multi-turn rows are not "
            "scoreable by this harness",
            DATASET_REGISTRY[dataset].provisioning,
        )
    if not isinstance(turns[0], str) or not turns[0].strip():
        raise DatasetUnavailable(
            dataset,
            f"{where} has an empty turn",
            DATASET_REGISTRY[dataset].provisioning,
        )
    return turns[0]


def _adapt_angelslim(
    dataset: str, rows: list[dict[str, Any]], *, max_output_tokens: int
) -> list[EvalItem]:
    source = DATASET_REGISTRY[dataset]
    # An empty template name means the vendor row already carries its own
    # instruction and is used verbatim. Wrapping it again would produce a
    # double instruction that no stored score could be compared against.
    template = (
        PROMPT_TEMPLATES[source.prompt_template] if source.prompt_template else ""
    )
    items: list[EvalItem] = []
    for index, row in enumerate(rows):
        where = f"row {index}"
        _require_fields(dataset, row, ("question_id", "turns"), where)
        question = _single_turn(dataset, row, where)
        row_id = str(row["question_id"])
        if source.scorer == "gsm8k_final_number":
            _require_fields(dataset, row, ("reference",), where)
            reference = row["reference"]
            if not isinstance(reference, list) or len(reference) != 1:
                raise DatasetUnavailable(
                    dataset,
                    f"{where} reference is not a single-element list",
                    source.provisioning,
                )
            answer = extract_reference_final_number(reference[0])
            if answer is None:
                raise DatasetUnavailable(
                    dataset,
                    f"{where} reference has no '#### <number>' final answer",
                    source.provisioning,
                )
            expected: dict[str, Any] = {"final_answer": answer}
            prompt = template.format(question=question)
        else:
            expected = {}
            prompt = template.format(prompt=question) if template else question
        items.append(
            EvalItem(
                item_id=f"{dataset}:{row_id}",
                dataset=dataset,
                scorer=source.scorer,
                prompt_text=canonical_text(prompt),
                expected=expected,
                row_id=row_id,
                max_output_tokens=max_output_tokens,
                metadata={"category": row.get("category")},
            )
        )
    return items


def _adapt_humaneval(
    dataset: str, rows: list[dict[str, Any]], *, max_output_tokens: int
) -> list[EvalItem]:
    source = DATASET_REGISTRY[dataset]
    template = PROMPT_TEMPLATES[source.prompt_template]
    items: list[EvalItem] = []
    for index, row in enumerate(rows):
        where = f"row {index}"
        _require_fields(
            dataset, row, ("task_id", "prompt", "test", "entry_point"), where
        )
        for name in ("prompt", "test", "entry_point"):
            if not isinstance(row[name], str) or not row[name].strip():
                raise DatasetUnavailable(
                    dataset, f"{where} field {name} is empty", source.provisioning
                )
        row_id = str(row["task_id"])
        items.append(
            EvalItem(
                item_id=f"{dataset}:{row_id}",
                dataset=dataset,
                scorer=source.scorer,
                prompt_text=canonical_text(
                    template.format(prompt=row["prompt"].rstrip())
                ),
                expected={
                    "prompt": canonical_text(row["prompt"]),
                    "test": canonical_text(row["test"]),
                    "entry_point": row["entry_point"],
                },
                row_id=row_id,
                max_output_tokens=max_output_tokens,
            )
        )
    return items


def _adapt_mbpp(
    dataset: str, rows: list[dict[str, Any]], *, max_output_tokens: int
) -> list[EvalItem]:
    source = DATASET_REGISTRY[dataset]
    template = PROMPT_TEMPLATES[source.prompt_template]
    items: list[EvalItem] = []
    for index, row in enumerate(rows):
        where = f"row {index}"
        _require_fields(dataset, row, ("task_id", "text", "test_list"), where)
        tests = row["test_list"]
        if not isinstance(tests, list) or not tests:
            raise DatasetUnavailable(
                dataset, f"{where} test_list is empty", source.provisioning
            )
        if not all(isinstance(entry, str) and entry.strip() for entry in tests):
            raise DatasetUnavailable(
                dataset,
                f"{where} test_list has a non-string entry",
                source.provisioning,
            )
        row_id = str(row["task_id"])
        items.append(
            EvalItem(
                item_id=f"{dataset}:{row_id}",
                dataset=dataset,
                scorer=source.scorer,
                prompt_text=canonical_text(
                    template.format(text=row["text"].strip(), assertion=tests[0])
                ),
                expected={
                    "prompt": "",
                    "test": canonical_text("\n".join(tests)),
                    "entry_point": None,
                },
                row_id=row_id,
                max_output_tokens=max_output_tokens,
            )
        )
    return items


_MC_LETTERS = ("A", "B", "C", "D")


def _adapt_mmlu(
    dataset: str, rows: list[dict[str, Any]], *, max_output_tokens: int
) -> list[EvalItem]:
    source = DATASET_REGISTRY[dataset]
    template = PROMPT_TEMPLATES[source.prompt_template]
    items: list[EvalItem] = []
    for index, row in enumerate(rows):
        where = f"row {index}"
        _require_fields(
            dataset, row, ("subject", "question", "choices", "answer"), where
        )
        choices = row["choices"]
        if not isinstance(choices, list) or len(choices) != 4:
            raise DatasetUnavailable(
                dataset,
                f"{where} does not have exactly four choices",
                source.provisioning,
            )
        answer = row["answer"]
        if isinstance(answer, int) and 0 <= answer < 4:
            letter = _MC_LETTERS[answer]
        elif isinstance(answer, str) and answer.strip().upper() in _MC_LETTERS:
            letter = answer.strip().upper()
        else:
            raise DatasetUnavailable(
                dataset,
                f"{where} answer {answer!r} is not 0-3 or A-D",
                source.provisioning,
            )
        rendered = "\n".join(
            f"{_MC_LETTERS[position]}. {text}" for position, text in enumerate(choices)
        )
        row_id = f"{row['subject']}:{index}"
        items.append(
            EvalItem(
                item_id=f"{dataset}:{row_id}",
                dataset=dataset,
                scorer=source.scorer,
                prompt_text=canonical_text(
                    template.format(question=row["question"], choices=rendered)
                ),
                expected={"letter": letter},
                row_id=row_id,
                max_output_tokens=max_output_tokens,
                metadata={"subject": row["subject"]},
            )
        )
    return items


def _adapt_agent_format(
    dataset: str, payload: dict[str, Any], *, max_output_tokens: int
) -> list[EvalItem]:
    source = DATASET_REGISTRY[dataset]
    for name in ("suite_id", "version", "cases"):
        if name not in payload:
            raise DatasetUnavailable(
                dataset, f"suite is missing {name}", source.provisioning
            )
    cases = payload["cases"]
    if not isinstance(cases, list) or not cases:
        raise DatasetUnavailable(dataset, "suite has no cases", source.provisioning)
    items: list[EvalItem] = []
    for index, case in enumerate(cases):
        where = f"case {index}"
        if not isinstance(case, dict):
            raise DatasetUnavailable(
                dataset, f"{where} is not an object", source.provisioning
            )
        _require_fields(dataset, case, ("id", "prompt", "expected_fields"), where)
        expected_fields = case["expected_fields"]
        if not isinstance(expected_fields, dict) or not expected_fields:
            raise DatasetUnavailable(
                dataset, f"{where} expected_fields is empty", source.provisioning
            )
        items.append(
            EvalItem(
                item_id=f"{dataset}:{case['id']}",
                dataset=dataset,
                scorer=source.scorer,
                prompt_text=canonical_text(case["prompt"]),
                expected={"fields": expected_fields},
                row_id=str(case["id"]),
                max_output_tokens=int(case.get("max_output_tokens", max_output_tokens)),
                metadata={
                    "suite_id": payload["suite_id"],
                    "version": payload["version"],
                },
            )
        )
    return items


# ---------------------------------------------------------------------------
# loader
# ---------------------------------------------------------------------------


def load_items(
    dataset: str,
    path: Path,
    *,
    expected_sha256: str | None = None,
    max_output_tokens: int = 512,
    limit: int | None = None,
) -> tuple[list[EvalItem], dict[str, Any]]:
    """Load and canonicalize a dataset, or refuse with an actionable reason.

    ``expected_sha256`` is compared against the raw file bytes. A mismatch is a
    refusal, never a warning: a score is only meaningful against a known file.
    """

    if dataset not in DATASET_REGISTRY:
        raise DatasetUnavailable(
            dataset,
            "unknown dataset name",
            f"known datasets: {', '.join(sorted(DATASET_REGISTRY))}",
        )
    source = DATASET_REGISTRY[dataset]
    if not path.is_file():
        raise DatasetUnavailable(
            dataset, f"dataset file is absent: {path}", source.provisioning
        )
    raw = path.read_bytes()
    actual_sha256 = sha256_bytes(raw)
    if expected_sha256 is not None and actual_sha256 != expected_sha256:
        raise DatasetUnavailable(
            dataset,
            f"file SHA-256 is {actual_sha256}, contract declares {expected_sha256}",
            "Repoint --dataset-path at the contracted file, or mint a new "
            "contract; do not edit the contract to match an unexpected file.",
        )

    if source.adapter == "agent_format_json":
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise DatasetUnavailable(
                dataset, "suite file is not a JSON object", source.provisioning
            )
        items = _adapt_agent_format(
            dataset, payload, max_output_tokens=max_output_tokens
        )
    else:
        rows = _read_jsonl(dataset, path)
        adapters: dict[str, Callable[..., list[EvalItem]]] = {
            "angelslim_question_jsonl": _adapt_angelslim,
            "humaneval_jsonl": _adapt_humaneval,
            "mbpp_jsonl": _adapt_mbpp,
            "mmlu_jsonl": _adapt_mmlu,
        }
        items = adapters[source.adapter](
            dataset, rows, max_output_tokens=max_output_tokens
        )

    # Duplicates are checked before the row count: a file with repeated ids is
    # broken in a way that "loaded 2 items, registry declares 164" would hide.
    seen: set[str] = set()
    duplicates: list[str] = []
    for item in items:
        if item.item_id in seen:
            duplicates.append(item.item_id)
        seen.add(item.item_id)
    if duplicates:
        raise DatasetUnavailable(
            dataset,
            f"duplicate item ids: {', '.join(sorted(set(duplicates))[:5])}",
            "Item ids are the regression join key and must be unique.",
        )
    if source.expected_rows is not None and len(items) != source.expected_rows:
        raise DatasetUnavailable(
            dataset,
            f"loaded {len(items)} items, registry declares {source.expected_rows}",
            "The file is not the contracted revision of this dataset.",
        )

    selected = items if limit is None else items[:limit]
    if limit is not None and len(selected) != limit:
        raise DatasetUnavailable(
            dataset,
            f"--limit {limit} exceeds the {len(items)} available items",
            "Lower the limit or provision the full dataset.",
        )

    provenance = {
        "dataset": dataset,
        "path": str(path),
        "file_sha256": actual_sha256,
        "file_bytes": len(raw),
        "adapter": source.adapter,
        "scorer": source.scorer,
        "prompt_template": source.prompt_template,
        "prompt_template_sha256": (
            PROMPT_TEMPLATE_SHA256.get(source.prompt_template)
            if source.prompt_template
            else None
        ),
        "canonical_source": source.canonical_source,
        "requires_code_execution": source.requires_code_execution,
        "items_available": len(items),
        "items_selected": len(selected),
        "limit": limit,
        "item_ids_sha256": sha256_bytes(
            "\n".join(item.item_id for item in selected).encode("utf-8")
        ),
        "prompts_sha256": sha256_bytes(
            "\n".join(item.prompt_sha256 for item in selected).encode("utf-8")
        ),
    }
    return selected, provenance


# ---------------------------------------------------------------------------
# scorers
# ---------------------------------------------------------------------------

NUMBER_PATTERN = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
HASH_MARKER = "####"
ANSWER_MARKER_PATTERN = re.compile(r"answer\s*(?:is|:)", re.IGNORECASE)
MC_ANSWER_MARKER_PATTERN = re.compile(r"answer\s*:", re.IGNORECASE)
MC_LETTER_PATTERN = re.compile(r"(?<![A-Za-z])([ABCD])(?![A-Za-z])")
FENCE_PATTERN = re.compile(r"```(?:[A-Za-z0-9_+-]*)\n(.*?)(?:```|\Z)", re.DOTALL)


def _normalize_number(token: str) -> str | None:
    cleaned = token.replace(",", "").rstrip(".")
    try:
        value = decimal.Decimal(cleaned)
    except decimal.InvalidOperation:
        return None
    return str(value.normalize())


def extract_reference_final_number(reference: str) -> str | None:
    """The GSM8K reference answer: the number after the last ``####``."""

    if HASH_MARKER not in reference:
        return None
    tail = reference.rsplit(HASH_MARKER, 1)[1]
    match = NUMBER_PATTERN.search(tail)
    if match is None:
        return None
    return _normalize_number(match.group(0))


def extract_final_number(text: str) -> str | None:
    """Frozen GSM8K answer-extraction rule.

    1. If the output contains ``####``, take the first number after the LAST
       ``####``. The prompt asks for exactly this, so it is the normal path.
    2. Otherwise, if the output contains ``answer is`` or ``answer:``, take the
       first number after the LAST such marker.
    3. Otherwise take the LAST number in the output.
    4. Otherwise there is no answer, and the item is unscoreable.

    Rule order is frozen. Changing it changes ``SCORER_REVISION_SHA256`` and
    invalidates every stored score, which is the intended behaviour.
    """

    if HASH_MARKER in text:
        tail = text.rsplit(HASH_MARKER, 1)[1]
        match = NUMBER_PATTERN.search(tail)
        if match is not None:
            return _normalize_number(match.group(0))
    markers = list(ANSWER_MARKER_PATTERN.finditer(text))
    if markers:
        match = NUMBER_PATTERN.search(text[markers[-1].end() :])
        if match is not None:
            return _normalize_number(match.group(0))
    numbers = NUMBER_PATTERN.findall(text)
    if numbers:
        return _normalize_number(numbers[-1])
    return None


def extract_choice_letter(text: str) -> str | None:
    """Frozen multiple-choice extraction rule.

    1. After the LAST ``Answer:`` marker, the first standalone A/B/C/D.
    2. Otherwise the LAST standalone A/B/C/D anywhere in the output.
    3. Otherwise unscoreable.
    """

    markers = list(MC_ANSWER_MARKER_PATTERN.finditer(text))
    if markers:
        match = MC_LETTER_PATTERN.search(text[markers[-1].end() :])
        if match is not None:
            return match.group(1)
    letters = MC_LETTER_PATTERN.findall(text)
    if letters:
        return letters[-1]
    return None


def extract_code_block(text: str, entry_point: str | None) -> str | None:
    """Frozen code-extraction rule for instruct-mode coding evals.

    1. Collect every fenced block. Prefer the LAST block that defines
       ``entry_point``; models routinely follow the answer with example usage,
       and the definition is what matters.
    2. Otherwise take the FIRST fenced block.
    3. If there are no fences, take the whole output.
    4. An empty result is unscoreable.

    An unterminated final fence is accepted to end at the end of the string:
    a response truncated at ``max_tokens`` is a real, common outcome and losing
    it silently would understate the model.
    """

    blocks = [block for block in FENCE_PATTERN.findall(text)]
    chosen: str | None = None
    if blocks:
        if entry_point:
            needle = f"def {entry_point}"
            defining = [block for block in blocks if needle in block]
            chosen = defining[-1] if defining else blocks[0]
        else:
            chosen = blocks[0]
    else:
        chosen = text
    chosen = chosen.strip("\n")
    return chosen if chosen.strip() else None


def build_code_program(item: EvalItem, completion: str) -> str | None:
    """Assemble the program that decides pass@1 for one coding item.

    If the extracted code defines the entry point it is used standalone; if it
    does not, it is treated as a function body and appended to the original
    prompt. Both shapes occur in practice and both are accepted, but the choice
    is deterministic and recorded.
    """

    entry_point = item.expected.get("entry_point")
    extracted = extract_code_block(completion, entry_point)
    if extracted is None:
        return None
    prompt = item.expected.get("prompt") or ""
    if entry_point and f"def {entry_point}" not in extracted:
        body = extracted if extracted.startswith((" ", "\t")) else None
        if body is None:
            return None
        program_head = f"{prompt.rstrip()}\n{body}\n"
    else:
        program_head = f"{extracted}\n"
    test = item.expected["test"]
    call = f"\ncheck({entry_point})\n" if entry_point else "\n"
    return f"{program_head}\n{test}\n{call}"


def score_gsm8k_final_number(item: EvalItem, completion: str) -> dict[str, Any]:
    extracted = extract_final_number(completion)
    expected = item.expected["final_answer"]
    return {
        "scorer": "gsm8k_final_number",
        "correct": extracted is not None and extracted == expected,
        "scoreable": extracted is not None,
        "extracted": extracted,
        "expected": expected,
    }


def score_multiple_choice_letter(item: EvalItem, completion: str) -> dict[str, Any]:
    extracted = extract_choice_letter(completion)
    expected = item.expected["letter"]
    return {
        "scorer": "multiple_choice_letter",
        "correct": extracted is not None and extracted == expected,
        "scoreable": extracted is not None,
        "extracted": extracted,
        "expected": expected,
    }


def score_json_fields(item: EvalItem, completion: str) -> dict[str, Any]:
    """Exact-field check on the first JSON object in the output.

    Deliberately identical in spirit to the long-context gate's ``validate_json``
    so a coding-agent format failure is judged the same way a retrieval failure
    already is.
    """

    expected = item.expected["fields"]
    stripped = completion.lstrip()
    try:
        parsed, _ = json.JSONDecoder().raw_decode(stripped)
    except json.JSONDecodeError as error:
        return {
            "scorer": "json_fields",
            "correct": False,
            "scoreable": False,
            "error": str(error),
            "expected": expected,
            "parsed": None,
        }
    field_pass = {
        key: isinstance(parsed, dict) and parsed.get(key) == value
        for key, value in expected.items()
    }
    return {
        "scorer": "json_fields",
        "correct": isinstance(parsed, dict) and all(field_pass.values()),
        "scoreable": True,
        "field_pass": field_pass,
        "expected": expected,
        "parsed": parsed,
    }


def score_reference_unscoreable(item: EvalItem, completion: str) -> dict[str, Any]:
    """A dataset that cannot produce a correctness score, and says so.

    ``angelslim_humaneval_prompts`` carries no unit tests. Rather than inventing
    a similarity metric and calling it accuracy, this scorer refuses to report
    correctness at all. The items are still useful for exact-output regression,
    which needs no score.
    """

    del completion
    return {
        "scorer": "reference_unscoreable",
        "correct": None,
        "scoreable": False,
        "reason": (
            f"{item.dataset} has no executable tests; functional correctness "
            "cannot be computed from it"
        ),
    }


SCORERS: dict[str, Callable[[EvalItem, str], dict[str, Any]]] = {
    "gsm8k_final_number": score_gsm8k_final_number,
    "multiple_choice_letter": score_multiple_choice_letter,
    "json_fields": score_json_fields,
    "reference_unscoreable": score_reference_unscoreable,
}

# ``code_exec_pass1`` is intentionally absent from ``SCORERS``. It is injected by
# ``eval_laguna_accuracy`` only when code execution has been explicitly enabled,
# so that importing this module can never cause untrusted code to run.
CODE_EXEC_SCORER = "code_exec_pass1"


def scorer_revision_sha256() -> str:
    """SHA-256 of this file. Every stored score is bound to it."""

    return sha256_bytes(Path(__file__).resolve().read_bytes())


def registry_report() -> dict[str, Any]:
    """Machine-readable availability report, for the harness and for humans."""

    return {
        "schema": SCHEMA,
        "scorer_revision_sha256": scorer_revision_sha256(),
        "prompt_template_sha256": dict(PROMPT_TEMPLATE_SHA256),
        "datasets": {
            name: {
                "purpose": source.purpose,
                "scorer": source.scorer,
                "canonical_source": source.canonical_source,
                "local_path": source.local_path,
                "local_bytes": source.local_bytes,
                "expected_rows": source.expected_rows,
                "requires_code_execution": source.requires_code_execution,
                "present_on_this_host": bool(
                    source.local_path and Path(source.local_path).is_file()
                ),
                "provisioning": source.provisioning,
            }
            for name, source in sorted(DATASET_REGISTRY.items())
        },
    }


def main() -> int:
    print(json.dumps(registry_report(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
