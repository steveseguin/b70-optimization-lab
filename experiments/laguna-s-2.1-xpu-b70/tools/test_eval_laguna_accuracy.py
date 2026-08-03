#!/usr/bin/env python3
"""CPU-only tests for the Laguna accuracy harness.

Everything is exercised against stubs: a stub tokenizer, a stub transport, a
stub Prometheus snapshot, and synthetic server logs built from the fork's own
frozen selector contract. No model is loaded, no endpoint is contacted, no
device is touched, and no model-written code is executed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_laguna_accuracy as harness
import eval_laguna_datasets as datasets
import eval_laguna_sandbox as sandbox
import validate_laguna_worker_selector_evidence as selectors

VLLM_COMMIT = "1234ff004d57f1f0c102bd2afff9690c16bf995a"
KERNELS_COMMIT = "a67a396245696a9df2a8929b445c721fa8899c92"
DSO_SHA256 = "b" * 64


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


class StubTokenizer:
    """Deterministic stand-in for the checkpoint tokenizer.

    Returns a length-prefixed byte encoding so distinct prompts get distinct
    token arrays, which is all the harness needs from a tokenizer.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def apply_chat_template(
        self, messages: list[dict[str, str]], **kwargs: Any
    ) -> list[int]:
        self.calls.append({"messages": messages, "kwargs": kwargs})
        content = messages[0]["content"]
        return [1, 2, 3, *content.encode("utf-8")[:24], 4]


def worker_log_lines(*, exact_prefill: bool = False) -> list[str]:
    expected = (
        selectors.LATENCY_EXPECTED_SELECTORS
        if exact_prefill
        else selectors.EXPECTED_SELECTORS
    )
    schema = selectors.LATENCY_SCHEMA if exact_prefill else selectors.SCHEMA
    marker = selectors.LATENCY_MARKER if exact_prefill else selectors.MARKER
    contract = (
        selectors.LATENCY_SELECTOR_CONTRACT_SHA256
        if exact_prefill
        else selectors.SELECTOR_CONTRACT_SHA256
    )
    lines = []
    for rank in range(4):
        record = {
            "schema": schema,
            "pid": 5000 + rank,
            "pid_start_time_ticks": 900 + rank,
            "worker_name": f"Worker_TP{rank}_EP{rank}",
            "world_size": 4,
            "ranks": {"global": rank, "local": rank, "tp": rank, "ep": rank},
            "selector_contract_sha256": contract,
            "selector_count": len(expected),
            "selectors": expected,
        }
        encoded = json.dumps(record, sort_keys=True, separators=(",", ":"))
        lines.append(f"(Worker_TP{rank}_EP{rank}) {marker} {encoded}")
    return lines


def build_server_log(
    tmp_path: Path,
    *,
    batched: int = 8192,
    scheduled: int = 8182,
    prefix_caching: str = "False",
    exact_prefill: bool = False,
) -> Path:
    lines = [
        "INFO non-default args: {'model': 'laguna', 'max_num_seqs': 1}",
        f"INFO Initializing a V1 LLM engine with config: enable_prefix_caching="
        f"{prefix_caching}, block_size=64",
        f"INFO Chunked prefill is enabled with max_num_batched_tokens={batched}.",
        f"INFO max_num_scheduled_tokens is set to {scheduled} based on speculation",
        *worker_log_lines(exact_prefill=exact_prefill),
    ]
    path = tmp_path / "server.log"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def build_map_evidence(tmp_path: Path, *, sha256: str = DSO_SHA256) -> Path:
    records = [
        {
            "global_rank": rank,
            "pid": 5000 + rank,
            "pid_start_time_ticks": 900 + rank,
            "path": "/opt/kernels/libgrouped_gemm_xe_2.so",
            "device_major": 259,
            "device_minor": 2,
            "inode": 4242,
            "sha256": sha256,
        }
        for rank in range(4)
    ]
    path = tmp_path / "maps.jsonl"
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    return path


def build_contract(tmp_path: Path, **overrides: Any) -> Path:
    dataset_path = tmp_path / "mmlu.jsonl"
    dataset_path.write_text(
        "".join(
            json.dumps(
                {
                    "subject": "logic",
                    "question": f"q{index}",
                    "choices": ["w", "x", "y", "z"],
                    "answer": index % 4,
                }
            )
            + "\n"
            for index in range(3)
        ),
        encoding="utf-8",
    )
    contract: dict[str, Any] = {
        "schema": harness.CONTRACT_SCHEMA,
        "contract_id": "laguna-accuracy-test-v1",
        "endpoint": {
            "base_url": "http://127.0.0.1:18080",
            "served_model_name": "laguna-s-2.1-int4",
        },
        "model_identity": {
            "target_revision": "4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb",
            "draft_revision": "5e07c246915c86dc6920fead03d019989224f2ba",
            "tokenizer_files_sha256": {},
        },
        "resolved_config": {
            "max_num_batched_tokens": 8192,
            "max_num_scheduled_tokens": 8182,
            "max_num_seqs": 1,
            "speculative": {
                "draft_sample_method": "greedy",
                "rejection_sample_method": "standard",
                "num_speculative_tokens": 11,
            },
        },
        "selector_profile": "q12",
        "build_identity": {
            "vllm_commit": VLLM_COMMIT,
            "kernels_commit": KERNELS_COMMIT,
            "grouped_gemm_dso_sha256": DSO_SHA256,
        },
        "sampling": {"temperature": 0, "top_p": 1, "seed": 1, "ignore_eos": False},
        "revisions": {
            "scorer_revision_sha256": datasets.scorer_revision_sha256(),
            "sandbox_revision_sha256": harness.sha256_bytes(
                Path(sandbox.__file__).resolve().read_bytes()
            ),
            "prompt_template_sha256": dict(datasets.PROMPT_TEMPLATE_SHA256),
        },
        "datasets": [
            {
                "name": "mmlu_multiple_choice",
                "path": str(dataset_path),
                "max_output_tokens": 32,
            }
        ],
    }
    contract.update(overrides)
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(contract, indent=2, sort_keys=True), encoding="utf-8")
    return path


def make_item(item_id: str = "d:1", scorer: str = "multiple_choice_letter"):
    return datasets.EvalItem(
        item_id=item_id,
        dataset="d",
        scorer=scorer,
        prompt_text=f"prompt for {item_id}",
        expected={"letter": "B"},
        row_id=item_id.split(":")[-1],
        max_output_tokens=32,
    )


def stub_send(text: str = "Answer: B", finish: str = "stop", tokens: int = 4):
    def send(**kwargs: Any) -> dict[str, Any]:
        ids = list(range(100, 100 + tokens))
        return {
            "request_id": kwargs["request_id"],
            "elapsed_s": 0.01,
            "token_ids": ids,
            "prompt_token_ids_returned": kwargs["prompt_ids"],
            "usage": {
                "prompt_tokens": len(kwargs["prompt_ids"]),
                "completion_tokens": len(ids),
                "prompt_tokens_details": {"cached_tokens": 0},
            },
            "finish_reason": finish,
            "text": text,
            "text_sha256": harness.sha256_bytes(text.encode()),
        }

    return send


def stub_snapshot():
    """Counters that advance by exactly one between the before and after reads.

    That is what a serial, non-batched request looks like: one prefill and one
    decode attributable to this request and nothing else.
    """

    state = {"n": 0.0}

    def snapshot() -> dict[str, float]:
        value = state["n"]
        state["n"] += 1.0
        return {name: value for name in harness.METRIC_NAMES}

    return snapshot


# ---------------------------------------------------------------------------
# contract
# ---------------------------------------------------------------------------


def test_contract_requires_every_attribution_section(tmp_path: Path) -> None:
    path = build_contract(tmp_path)
    payload = json.loads(path.read_text())
    del payload["build_identity"]
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="missing: build_identity"):
        harness.load_contract(path)


def test_contract_rejects_a_foreign_schema(tmp_path: Path) -> None:
    path = build_contract(tmp_path, schema="something-else")
    with pytest.raises(ValueError, match="contract schema"):
        harness.load_contract(path)


def test_contract_rejects_an_unknown_selector_profile(tmp_path: Path) -> None:
    path = build_contract(tmp_path, selector_profile="q99")
    with pytest.raises(ValueError, match="unknown selector_profile"):
        harness.load_contract(path)


def test_contract_rejects_an_empty_dataset_list(tmp_path: Path) -> None:
    path = build_contract(tmp_path, datasets=[])
    with pytest.raises(ValueError, match="no datasets"):
        harness.load_contract(path)


# ---------------------------------------------------------------------------
# revision binding
# ---------------------------------------------------------------------------


def test_scorer_revision_drift_is_refused(tmp_path: Path) -> None:
    contract = json.loads(build_contract(tmp_path).read_text())
    contract["revisions"]["scorer_revision_sha256"] = "0" * 64
    refusals = harness.Refusals()
    harness.check_revisions(contract, refusals)
    kinds = [entry["kind"] for entry in refusals.entries]
    assert "scorer_revision_drift" in kinds


def test_prompt_template_drift_is_refused(tmp_path: Path) -> None:
    contract = json.loads(build_contract(tmp_path).read_text())
    contract["revisions"]["prompt_template_sha256"]["gsm8k_v1"] = "0" * 64
    refusals = harness.Refusals()
    harness.check_revisions(contract, refusals)
    entries = [e for e in refusals.entries if e["kind"] == "prompt_template_drift"]
    assert entries and "gsm8k_v1" in entries[0]["detail"]


def test_matching_revisions_produce_no_refusal(tmp_path: Path) -> None:
    contract = json.loads(build_contract(tmp_path).read_text())
    refusals = harness.Refusals()
    record = harness.check_revisions(contract, refusals)
    assert not refusals
    assert record["scorer_revision_sha256"] == datasets.scorer_revision_sha256()


# ---------------------------------------------------------------------------
# attribution
# ---------------------------------------------------------------------------


def test_attribution_binds_selectors_partition_and_dso(tmp_path: Path) -> None:
    contract = json.loads(build_contract(tmp_path).read_text())
    refusals = harness.Refusals()
    attribution = harness.collect_attribution(
        contract,
        server_log=build_server_log(tmp_path),
        map_evidence=build_map_evidence(tmp_path),
        vllm_commit=VLLM_COMMIT,
        kernels_commit=KERNELS_COMMIT,
        refusals=refusals,
    )
    assert not refusals.entries, refusals.entries
    assert len(attribution["worker_selector_records"]) == 4
    assert attribution["resolved_cache_partition"]["resolved"] == {
        "enable_prefix_caching": False,
        "max_num_partial_prefills": 1,
        "max_num_batched_tokens": 8192,
        "max_num_scheduled_tokens": 8182,
    }
    assert attribution["selector_contract_sha256"] == (
        selectors.SELECTOR_CONTRACT_SHA256
    )
    assert attribution["vllm_commit"] == VLLM_COMMIT
    assert attribution["server_log_sha256"]


def test_attribution_refuses_a_partition_that_is_not_the_contracted_one(
    tmp_path: Path,
) -> None:
    """The 2026-08-02 finding, encoded as a gate.

    An 8192/8064 partition rewrote output token IDs on every long row. A score
    collected on a different partition is not comparable to one collected on
    the contracted partition, so it is refused rather than reported.
    """

    contract = json.loads(build_contract(tmp_path).read_text())
    refusals = harness.Refusals()
    harness.collect_attribution(
        contract,
        server_log=build_server_log(tmp_path, batched=8202, scheduled=8192),
        map_evidence=build_map_evidence(tmp_path),
        vllm_commit=VLLM_COMMIT,
        kernels_commit=KERNELS_COMMIT,
        refusals=refusals,
    )
    kinds = [entry["kind"] for entry in refusals.entries]
    assert "resolved_partition_invalid" in kinds


def test_attribution_refuses_prefix_caching(tmp_path: Path) -> None:
    contract = json.loads(build_contract(tmp_path).read_text())
    refusals = harness.Refusals()
    harness.collect_attribution(
        contract,
        server_log=build_server_log(tmp_path, prefix_caching="True"),
        map_evidence=build_map_evidence(tmp_path),
        vllm_commit=VLLM_COMMIT,
        kernels_commit=KERNELS_COMMIT,
        refusals=refusals,
    )
    kinds = [entry["kind"] for entry in refusals.entries]
    assert "resolved_partition_invalid" in kinds


def test_attribution_refuses_a_selector_set_that_is_not_the_profile(
    tmp_path: Path,
) -> None:
    contract = json.loads(build_contract(tmp_path).read_text())
    contract["selector_profile"] = "q12-wide-prefill"
    refusals = harness.Refusals()
    harness.collect_attribution(
        contract,
        server_log=build_server_log(tmp_path),
        map_evidence=build_map_evidence(tmp_path),
        vllm_commit=VLLM_COMMIT,
        kernels_commit=KERNELS_COMMIT,
        refusals=refusals,
    )
    kinds = [entry["kind"] for entry in refusals.entries]
    assert "selector_evidence_invalid" in kinds


def test_attribution_refuses_a_dso_that_is_not_the_contracted_one(
    tmp_path: Path,
) -> None:
    contract = json.loads(build_contract(tmp_path).read_text())
    refusals = harness.Refusals()
    harness.collect_attribution(
        contract,
        server_log=build_server_log(tmp_path),
        map_evidence=build_map_evidence(tmp_path, sha256="c" * 64),
        vllm_commit=VLLM_COMMIT,
        kernels_commit=KERNELS_COMMIT,
        refusals=refusals,
    )
    kinds = [entry["kind"] for entry in refusals.entries]
    assert "dso_hash_drift" in kinds


def test_attribution_refuses_commit_drift(tmp_path: Path) -> None:
    contract = json.loads(build_contract(tmp_path).read_text())
    refusals = harness.Refusals()
    harness.collect_attribution(
        contract,
        server_log=build_server_log(tmp_path),
        map_evidence=build_map_evidence(tmp_path),
        vllm_commit="deadbeef",
        kernels_commit="cafebabe",
        refusals=refusals,
    )
    kinds = [entry["kind"] for entry in refusals.entries]
    assert "vllm_commit_drift" in kinds
    assert "kernels_commit_drift" in kinds


@pytest.mark.parametrize(
    ("mutation", "expected_kind"),
    [
        (
            {"sampling": {"temperature": 0.7, "top_p": 1, "ignore_eos": False}},
            "sampling_not_greedy",
        ),
        (
            {"sampling": {"temperature": 0, "top_p": 0.9, "ignore_eos": False}},
            "sampling_not_greedy",
        ),
        (
            {"sampling": {"temperature": 0, "top_p": 1, "ignore_eos": True}},
            "sampling_not_greedy",
        ),
    ],
)
def test_attribution_refuses_non_greedy_sampling(
    tmp_path: Path, mutation: dict, expected_kind: str
) -> None:
    contract = json.loads(build_contract(tmp_path).read_text())
    contract.update(mutation)
    refusals = harness.Refusals()
    harness.collect_attribution(
        contract,
        server_log=build_server_log(tmp_path),
        map_evidence=build_map_evidence(tmp_path),
        vllm_commit=VLLM_COMMIT,
        kernels_commit=KERNELS_COMMIT,
        refusals=refusals,
    )
    assert expected_kind in [entry["kind"] for entry in refusals.entries]


def test_attribution_refuses_lossy_speculative_sampling(tmp_path: Path) -> None:
    """Greedy rejection is what makes speculation output-lossless.

    Under ``rejection_greedy_sample_kernel`` the emitted token is the target
    argmax whether or not the draft was accepted. Change the rejection method
    and that guarantee is gone, so exact comparison stops being valid.
    """

    contract = json.loads(build_contract(tmp_path).read_text())
    contract["resolved_config"]["speculative"]["rejection_sample_method"] = "synthetic"
    refusals = harness.Refusals()
    harness.collect_attribution(
        contract,
        server_log=build_server_log(tmp_path),
        map_evidence=build_map_evidence(tmp_path),
        vllm_commit=VLLM_COMMIT,
        kernels_commit=KERNELS_COMMIT,
        refusals=refusals,
    )
    kinds = [entry["kind"] for entry in refusals.entries]
    assert "speculation_not_output_lossless" in kinds


def test_attribution_refuses_concurrent_batching(tmp_path: Path) -> None:
    contract = json.loads(build_contract(tmp_path).read_text())
    contract["resolved_config"]["max_num_seqs"] = 4
    refusals = harness.Refusals()
    harness.collect_attribution(
        contract,
        server_log=build_server_log(tmp_path),
        map_evidence=build_map_evidence(tmp_path),
        vllm_commit=VLLM_COMMIT,
        kernels_commit=KERNELS_COMMIT,
        refusals=refusals,
    )
    kinds = [entry["kind"] for entry in refusals.entries]
    assert "batching_not_serial" in kinds


# ---------------------------------------------------------------------------
# per-request invariants
# ---------------------------------------------------------------------------


def test_request_checks_pass_on_a_clean_row() -> None:
    ids = [1, 2, 3]
    row = {
        "token_ids": [9, 9],
        "prompt_token_ids_returned": ids,
        "usage": {
            "prompt_tokens": 3,
            "completion_tokens": 2,
            "prompt_tokens_details": {"cached_tokens": 0},
        },
        "finish_reason": "stop",
    }
    deltas = {
        f"{harness.PREFILL_TIME}_count": 1.0,
        f"{harness.DECODE_TIME}_count": 1.0,
    }
    assert all(harness.request_checks(row, ids, deltas).values())


def test_request_checks_catch_a_warm_cache_and_a_shared_step() -> None:
    ids = [1, 2, 3]
    row = {
        "token_ids": [9, 9],
        "prompt_token_ids_returned": ids,
        "usage": {
            "prompt_tokens": 3,
            "completion_tokens": 2,
            "prompt_tokens_details": {"cached_tokens": 64},
        },
        "finish_reason": "stop",
    }
    deltas = {
        f"{harness.PREFILL_TIME}_count": 2.0,
        f"{harness.DECODE_TIME}_count": 1.0,
    }
    checks = harness.request_checks(row, ids, deltas)
    assert checks["cache_zero"] is False
    assert checks["prefill_metric_count_one"] is False


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------


def test_code_execution_scorer_is_absent_unless_explicitly_enabled() -> None:
    off = harness.build_scorers(
        enable_code_execution=False,
        policy=sandbox.SandboxPolicy(),
        python_executable=sys.executable,
    )
    assert datasets.CODE_EXEC_SCORER not in off
    on = harness.build_scorers(
        enable_code_execution=True,
        policy=sandbox.SandboxPolicy(),
        python_executable=sys.executable,
    )
    assert datasets.CODE_EXEC_SCORER in on


def test_an_item_whose_scorer_is_disabled_is_incorrect_not_skipped() -> None:
    item = make_item(scorer=datasets.CODE_EXEC_SCORER)
    table = harness.build_scorers(
        enable_code_execution=False,
        policy=sandbox.SandboxPolicy(),
        python_executable=sys.executable,
    )
    result = harness.score_row(item, {"text": "x", "finish_reason": "stop"}, table)
    assert result["correct"] is False
    assert result["scoreable"] is False
    assert "--enable-code-execution" in result["reason"]


def test_a_truncated_response_is_flagged_and_still_scored() -> None:
    item = make_item()
    table = harness.build_scorers(
        enable_code_execution=False,
        policy=sandbox.SandboxPolicy(),
        python_executable=sys.executable,
    )
    result = harness.score_row(
        item, {"text": "Answer: B", "finish_reason": "length"}, table
    )
    assert result["truncated"] is True
    assert result["correct"] is True


def test_undefined_correctness_is_recorded_and_counted_as_incorrect() -> None:
    item = make_item(scorer="reference_unscoreable")
    table = harness.build_scorers(
        enable_code_execution=False,
        policy=sandbox.SandboxPolicy(),
        python_executable=sys.executable,
    )
    result = harness.score_row(item, {"text": "x", "finish_reason": "stop"}, table)
    assert result["correct"] is False
    assert result["correct_is_undefined"] is True


def test_aggregate_never_silently_drops_an_item() -> None:
    rows = [
        {"dataset": "a", "score": {"correct": True, "scoreable": True}},
        {"dataset": "a", "score": {"correct": False, "scoreable": True}},
        {
            "dataset": "a",
            "score": {"correct": False, "scoreable": False, "truncated": True},
        },
        {
            "dataset": "b",
            "score": {
                "correct": False,
                "scoreable": False,
                "correct_is_undefined": True,
            },
        },
    ]
    summary = harness.aggregate(rows)
    first = summary["by_dataset"]["a"]
    assert first["items"] == 3
    assert first["correct"] == 1
    assert first["unscoreable"] == 1
    assert first["truncated"] == 1
    # The unscoreable item stays in the denominator: it is a wrong answer, not
    # an absent one.
    assert first["accuracy_denominator"] == 3
    assert first["accuracy"] == pytest.approx(1 / 3)
    second = summary["by_dataset"]["b"]
    assert second["accuracy_denominator"] == 0
    assert second["accuracy"] is None
    assert summary["totals"]["items"] == 4


# ---------------------------------------------------------------------------
# determinism
# ---------------------------------------------------------------------------


def test_determinism_is_unverified_with_a_single_pass() -> None:
    summary = harness.determinism_summary([{"a": "h1"}], 1)
    assert summary["verified"] is False
    assert "asserted, not measured" in summary["reason"]


def test_determinism_is_verified_when_passes_agree() -> None:
    summary = harness.determinism_summary([{"a": "h1"}, {"a": "h1"}], 2)
    assert summary["verified"] is True
    assert summary["divergent_items"] == []


def test_determinism_names_every_divergent_item() -> None:
    summary = harness.determinism_summary(
        [{"a": "h1", "b": "h2"}, {"a": "h1", "b": "h3"}], 2
    )
    assert summary["verified"] is False
    assert summary["divergent_items"] == ["b"]


def test_a_missing_item_in_the_second_pass_counts_as_divergence() -> None:
    summary = harness.determinism_summary([{"a": "h1"}, {}], 2)
    assert summary["verified"] is False
    assert summary["divergent_items"] == ["a"]


# ---------------------------------------------------------------------------
# suite driver
# ---------------------------------------------------------------------------


def base_contract() -> dict[str, Any]:
    return {
        "endpoint": {
            "base_url": "http://127.0.0.1:18080",
            "served_model_name": "laguna-s-2.1-int4",
        },
        "sampling": {"temperature": 0, "top_p": 1, "seed": 1, "ignore_eos": False},
    }


def test_run_suite_sends_every_item_once_per_pass_in_order() -> None:
    items = [make_item(f"d:{index}") for index in range(3)]
    prompt_ids = {item.item_id: [1, 2, 3] for item in items}
    seen: list[str] = []

    def send(**kwargs: Any) -> dict[str, Any]:
        seen.append(kwargs["request_id"])
        return stub_send()(**kwargs)

    refusals = harness.Refusals()
    rows, passes = harness.run_suite(
        items=items,
        prompt_ids=prompt_ids,
        contract=base_contract(),
        replicates=2,
        timeout=5,
        scorer_table=dict(datasets.SCORERS),
        send=send,
        snapshot=stub_snapshot(),
        refusals=refusals,
    )
    assert not refusals.entries
    assert len(seen) == 6
    assert seen[0].startswith("laguna-acc-p0-0000-")
    assert seen[3].startswith("laguna-acc-p1-0000-")
    assert len(passes) == 2 and passes[0] == passes[1]
    assert sum(1 for row in rows if row["pass_index"] == 0) == 3
    # Only the first pass is scored; replicates exist to prove reproducibility.
    assert all("score" in row for row in rows if row["pass_index"] == 0)
    assert all("score" not in row for row in rows if row["pass_index"] == 1)


def test_run_suite_refuses_when_a_request_invariant_fails() -> None:
    items = [make_item()]

    def send(**kwargs: Any) -> dict[str, Any]:
        row = stub_send()(**kwargs)
        row["usage"]["prompt_tokens_details"]["cached_tokens"] = 128
        return row

    refusals = harness.Refusals()
    harness.run_suite(
        items=items,
        prompt_ids={items[0].item_id: [1, 2, 3]},
        contract=base_contract(),
        replicates=1,
        timeout=5,
        scorer_table=dict(datasets.SCORERS),
        send=send,
        snapshot=stub_snapshot(),
        refusals=refusals,
    )
    entries = [e for e in refusals.entries if e["kind"] == "request_invariant_failed"]
    assert entries and "cache_zero" in entries[0]["failed_checks"]


def test_run_suite_refuses_rather_than_skipping_a_failed_request() -> None:
    items = [make_item("d:1"), make_item("d:2")]

    def send(**kwargs: Any) -> dict[str, Any]:
        if "d:2" in kwargs["request_id"]:
            raise RuntimeError("HTTP 500: boom")
        return stub_send()(**kwargs)

    refusals = harness.Refusals()
    rows, _ = harness.run_suite(
        items=items,
        prompt_ids={item.item_id: [1, 2, 3] for item in items},
        contract=base_contract(),
        replicates=1,
        timeout=5,
        scorer_table=dict(datasets.SCORERS),
        send=send,
        snapshot=stub_snapshot(),
        refusals=refusals,
    )
    kinds = [entry["kind"] for entry in refusals.entries]
    assert "request_failed" in kinds
    assert "items_missing_from_pass" in kinds
    assert len(rows) == 1


def test_run_suite_refuses_on_prometheus_schema_drift() -> None:
    items = [make_item()]
    state = {"n": 0}

    def snapshot() -> dict[str, float]:
        state["n"] += 1
        if state["n"] == 1:
            return {name: 0.0 for name in harness.METRIC_NAMES}
        return {"unexpected_metric": 1.0}

    refusals = harness.Refusals()
    harness.run_suite(
        items=items,
        prompt_ids={items[0].item_id: [1, 2, 3]},
        contract=base_contract(),
        replicates=1,
        timeout=5,
        scorer_table=dict(datasets.SCORERS),
        send=stub_send(),
        snapshot=snapshot,
        refusals=refusals,
    )
    assert "metric_schema_drift" in [e["kind"] for e in refusals.entries]


# ---------------------------------------------------------------------------
# prompts
# ---------------------------------------------------------------------------


def test_prompt_ids_come_from_the_checkpoint_chat_template() -> None:
    tokenizer = StubTokenizer()
    ids = harness.build_prompt_ids(tokenizer, "hello")
    assert isinstance(ids, list) and all(isinstance(value, int) for value in ids)
    call = tokenizer.calls[0]
    assert call["messages"] == [{"role": "user", "content": "hello"}]
    assert call["kwargs"]["add_generation_prompt"] is True
    assert call["kwargs"]["enable_thinking"] is False
    assert call["kwargs"]["tokenize"] is True


def test_distinct_prompts_produce_distinct_token_arrays() -> None:
    tokenizer = StubTokenizer()
    assert harness.build_prompt_ids(tokenizer, "a") != harness.build_prompt_ids(
        tokenizer, "b"
    )


# ---------------------------------------------------------------------------
# end to end, no endpoint
# ---------------------------------------------------------------------------


def test_build_only_resolves_everything_and_contacts_nothing(tmp_path: Path) -> None:
    contract = build_contract(tmp_path)
    out = tmp_path / "out.json"
    code = harness.main(
        [
            "--contract",
            str(contract),
            "--out",
            str(out),
            "--model-path",
            str(tmp_path),
            "--build-only",
        ],
        tokenizer=StubTokenizer(),
    )
    assert code == 0
    payload = json.loads(out.read_text())
    assert payload["status"] == "BUILD_ONLY"
    assert payload["refusals"] == []
    assert len(payload["prompt_manifest"]) == 3
    assert payload["datasets"][0]["dataset"] == "mmlu_multiple_choice"
    assert payload["chat_template_kwargs"]["enable_thinking"] is False
    assert payload["code_execution_enabled"] is False
    assert all(entry["prompt_token_ids_sha256"] for entry in payload["prompt_manifest"])


def test_a_scoring_run_without_attribution_arguments_is_refused(tmp_path: Path) -> None:
    contract = build_contract(tmp_path)
    out = tmp_path / "out.json"
    code = harness.main(
        ["--contract", str(contract), "--out", str(out), "--model-path", str(tmp_path)],
        tokenizer=StubTokenizer(),
    )
    assert code == 2
    payload = json.loads(out.read_text())
    assert payload["status"] == harness.STATUS_REFUSED
    kinds = {entry["kind"] for entry in payload["refusals"]}
    assert kinds == {"attribution_argument_missing"}
    assert payload["rows"] == []


def test_an_absent_dataset_refuses_with_provisioning_instructions(
    tmp_path: Path,
) -> None:
    contract_path = build_contract(tmp_path)
    contract = json.loads(contract_path.read_text())
    contract["datasets"] = [
        {"name": "openai_humaneval", "path": str(tmp_path / "absent.jsonl")}
    ]
    contract_path.write_text(json.dumps(contract))
    out = tmp_path / "out.json"
    code = harness.main(
        [
            "--contract",
            str(contract_path),
            "--out",
            str(out),
            "--model-path",
            str(tmp_path),
            "--build-only",
        ],
        tokenizer=StubTokenizer(),
    )
    assert code == 0
    payload = json.loads(out.read_text())
    refusal = payload["refusals"][0]
    assert refusal["kind"] == "dataset_unavailable"
    assert "task_id" in refusal["provisioning"]


def test_code_execution_items_are_refused_unless_the_flag_is_given(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "mbpp.jsonl"
    dataset.write_text(
        json.dumps({"task_id": 1, "text": "t", "test_list": ["assert f(1)==1"]}) + "\n"
    )
    contract_path = build_contract(tmp_path)
    contract = json.loads(contract_path.read_text())
    contract["datasets"] = [{"name": "mbpp_sanitized", "path": str(dataset)}]
    contract_path.write_text(json.dumps(contract))
    out = tmp_path / "out.json"
    harness.main(
        [
            "--contract",
            str(contract_path),
            "--out",
            str(out),
            "--model-path",
            str(tmp_path),
            "--build-only",
        ],
        tokenizer=StubTokenizer(),
    )
    payload = json.loads(out.read_text())
    kinds = {entry["kind"] for entry in payload["refusals"]}
    assert "code_execution_not_enabled" in kinds


def test_tokenizer_drift_from_the_contracted_checkpoint_is_refused(
    tmp_path: Path,
) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "tokenizer.json").write_text("{}")
    contract_path = build_contract(tmp_path)
    contract = json.loads(contract_path.read_text())
    contract["model_identity"]["tokenizer_files_sha256"] = {"tokenizer.json": "0" * 64}
    contract_path.write_text(json.dumps(contract))
    out = tmp_path / "out.json"
    harness.main(
        [
            "--contract",
            str(contract_path),
            "--out",
            str(out),
            "--model-path",
            str(model_dir),
            "--build-only",
        ],
        tokenizer=StubTokenizer(),
    )
    payload = json.loads(out.read_text())
    kinds = {entry["kind"] for entry in payload["refusals"]}
    assert "tokenizer_drift" in kinds
