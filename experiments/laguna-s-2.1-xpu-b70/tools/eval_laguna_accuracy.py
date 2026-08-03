#!/usr/bin/env python3
"""Fail-closed accuracy harness for Laguna S 2.1 INT4 on an OpenAI endpoint.

Why this exists
---------------

The campaign has extraordinary evidence that kernel changes leave the model's
output *unchanged*: frozen oracles, bit-identical token IDs, cache-zero proofs.
It has never had any evidence that the output is *good*. The only quality
signals are a synthetic needle-in-haystack JSON retrieval check and
self-consistency against the model's own oracle -- neither of which can detect
that INT4 quantization, the offline Hadamard rotation, or TP4/EP4 sharding
damaged the model, because all three are baked into the oracle too.

This harness supplies the missing axis. It is the complement of bit-exactness,
not a replacement for it:

* **bit-exactness** proves *unchanged*, and is cheap enough to run per kernel;
* **accuracy** proves *good enough*, and is expensive, so it is run once per
  output-changing configuration.

Determinism is the design premise
---------------------------------

The serving configuration is greedy end to end (``temperature=0``, ``top_p=1``,
``draft_sample_method=greedy``, ``rejection_sample_method=standard``), and
``max_num_seqs=1``. Under the fork's ``rejection_greedy_sample_kernel`` the
non-synthetic branch stores ``token_id = target_argmax_id`` unconditionally --
the draft token is compared only to decide where the accepted run stops. So
speculation changes speed and not output, and draft depth or acceptance rate
cannot move a single output token. With prompts pinned as token IDs the whole
response is a pure function of weights, kernels, batch shapes and the prefill
partition. (The ``synthetic`` rejection branch is different and genuinely
random; :func:`collect_attribution` refuses it.)

That makes quality-regression detection *exact* rather than statistical: one
changed answer is signal, not noise. It also sets the bar for what the harness
must prove, because determinism has four known ways to break here, and every one
of them has an explicit check:

1. **Prefill partition.** Measured in this campaign on 2026-08-02: moving the
   32,640-token partition from ``8182+8182+8182+8094`` to ``8192+8192+8192+8064``
   changed output token IDs on all eight long rows. The resolved batched and
   derived scheduled budgets are read out of the server log and must match the
   contract exactly.
2. **Batch co-residency.** Two in-flight requests change the verifier width and
   therefore the reduction order. Requests are sent strictly serially and each
   one must move the prefill and decode Prometheus counters by exactly one.
3. **Prefix caching.** A shared prompt prefix would both warm the run and change
   numerics. ``enable_prefix_caching`` must resolve ``False`` and every row must
   report ``cached_tokens == 0``.
4. **Everything else.** Proved empirically rather than argued: with
   ``--replicates 2`` the whole suite is sent twice and every item's output
   token IDs must be identical across passes. A run that cannot reproduce itself
   cannot be minted as an oracle.

Fail-closed
-----------

Every attribution field is compared against a preregistered contract before a
single request is sent, and any mismatch is a refusal. Items are never silently
skipped: an item that cannot be scored is recorded as incorrect *and* counted in
``unscoreable_items``, and any refusal at all makes the whole run ``REFUSED``.

Safety
------

Importing or running this module with ``--build-only`` performs no network I/O,
loads no model, and touches no device. Code-execution scorers are refused unless
``--enable-code-execution`` is passed; see ``eval_laguna_sandbox`` for what that
boundary is and is not.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
import assert_laguna_resolved_cache_partition as partition  # noqa: E402
import eval_laguna_datasets as datasets  # noqa: E402
import eval_laguna_sandbox as sandbox  # noqa: E402
import validate_laguna_worker_selector_evidence as selectors  # noqa: E402

SCHEMA = "laguna-accuracy-eval-v1"
CONTRACT_SCHEMA = "laguna-accuracy-contract-v1"

PREFILL_TIME = "vllm:request_prefill_time_seconds"
DECODE_TIME = "vllm:request_decode_time_seconds"
SPEC_DRAFTS = "vllm:spec_decode_num_drafts_total"
SPEC_DRAFT_TOKENS = "vllm:spec_decode_num_draft_tokens_total"
SPEC_ACCEPTED = "vllm:spec_decode_num_accepted_tokens_total"

# Matches the long-context lane so prompts built by both tools are comparable.
CHAT_TEMPLATE_KWARGS = {"add_generation_prompt": True, "enable_thinking": False}

SELECTOR_PROFILES = {
    "q12": {"require_exact_prefill": False, "require_wide_prefill": False},
    "q12-exact-prefill": {"require_exact_prefill": True, "require_wide_prefill": False},
    "q12-wide-prefill": {"require_exact_prefill": True, "require_wide_prefill": True},
}

STATUS_PASS = "PASS_SCORED"
STATUS_PASS_UNVERIFIED = "PASS_SCORED_DETERMINISM_UNVERIFIED"
STATUS_REFUSED = "REFUSED"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def token_hash(token_ids: list[int]) -> str:
    return sha256_bytes(",".join(str(value) for value in token_ids).encode())


class Refusals:
    """Every reason the harness declined to produce a number, in order."""

    def __init__(self) -> None:
        self._entries: list[dict[str, Any]] = []

    def add(self, kind: str, detail: str, **extra: Any) -> None:
        self._entries.append({"kind": kind, "detail": detail, **extra})

    def add_record(self, record: dict[str, Any]) -> None:
        self._entries.append(record)

    def require(self, condition: bool, kind: str, detail: str, **extra: Any) -> bool:
        if not condition:
            self.add(kind, detail, **extra)
        return condition

    @property
    def entries(self) -> list[dict[str, Any]]:
        return list(self._entries)

    def __bool__(self) -> bool:
        return bool(self._entries)

    def __len__(self) -> int:
        return len(self._entries)


# ---------------------------------------------------------------------------
# contract
# ---------------------------------------------------------------------------

CONTRACT_REQUIRED = (
    "schema",
    "contract_id",
    "endpoint",
    "model_identity",
    "resolved_config",
    "selector_profile",
    "build_identity",
    "sampling",
    "revisions",
    "datasets",
)


def load_contract(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("contract is not a JSON object")
    missing = [name for name in CONTRACT_REQUIRED if name not in payload]
    if missing:
        raise ValueError(f"contract is missing: {', '.join(missing)}")
    if payload["schema"] != CONTRACT_SCHEMA:
        raise ValueError(
            f"contract schema is {payload['schema']!r}, expected {CONTRACT_SCHEMA!r}"
        )
    if payload["selector_profile"] not in SELECTOR_PROFILES:
        raise ValueError(
            f"unknown selector_profile {payload['selector_profile']!r}; "
            f"known: {', '.join(sorted(SELECTOR_PROFILES))}"
        )
    if not isinstance(payload["datasets"], list) or not payload["datasets"]:
        raise ValueError("contract declares no datasets")
    return payload


def check_revisions(contract: dict[str, Any], refusals: Refusals) -> dict[str, Any]:
    """Bind stored scores to the exact scoring and prompt logic that made them."""

    declared = contract["revisions"]
    actual_scorer = datasets.scorer_revision_sha256()
    actual_sandbox = sha256_bytes(Path(sandbox.__file__).resolve().read_bytes())
    refusals.require(
        declared.get("scorer_revision_sha256") == actual_scorer,
        "scorer_revision_drift",
        "eval_laguna_datasets.py does not match the contracted scorer revision; "
        "scores produced by different scoring logic are not comparable",
        contract=declared.get("scorer_revision_sha256"),
        actual=actual_scorer,
    )
    refusals.require(
        declared.get("sandbox_revision_sha256") == actual_sandbox,
        "sandbox_revision_drift",
        "eval_laguna_sandbox.py does not match the contracted sandbox revision",
        contract=declared.get("sandbox_revision_sha256"),
        actual=actual_sandbox,
    )
    declared_templates = declared.get("prompt_template_sha256") or {}
    for name, expected in sorted(declared_templates.items()):
        refusals.require(
            datasets.PROMPT_TEMPLATE_SHA256.get(name) == expected,
            "prompt_template_drift",
            f"prompt template {name} changed; every stored score for it is void",
            contract=expected,
            actual=datasets.PROMPT_TEMPLATE_SHA256.get(name),
        )
    return {
        "scorer_revision_sha256": actual_scorer,
        "sandbox_revision_sha256": actual_sandbox,
        "prompt_template_sha256": dict(datasets.PROMPT_TEMPLATE_SHA256),
    }


# ---------------------------------------------------------------------------
# attribution
# ---------------------------------------------------------------------------


def load_map_evidence(path: Path) -> list[dict[str, Any]]:
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(records) != 4:
        raise ValueError(
            f"expected four grouped-GEMM map records, found {len(records)}"
        )
    return records


def collect_attribution(
    contract: dict[str, Any],
    *,
    server_log: Path,
    map_evidence: Path,
    vllm_commit: str,
    kernels_commit: str,
    refusals: Refusals,
) -> dict[str, Any]:
    """Resolve what actually ran, and refuse if it is not what was contracted.

    Nothing here is taken from the launcher's argv. Selectors come from the
    worker records the fork prints on every rank, the cache and partition
    settings come from vLLM's own resolved-config logging, and the kernel
    identity comes from ``/proc/<pid>/maps`` evidence that the existing
    ``validate_laguna_worker_selector_evidence`` tool already wrote.
    """

    profile = SELECTOR_PROFILES[contract["selector_profile"]]
    resolved_selectors: list[dict[str, Any]] = []
    try:
        resolved_selectors = selectors.parse_worker_selector_log(
            server_log,
            require_exact_prefill=profile["require_exact_prefill"],
            require_wide_prefill=profile["require_wide_prefill"],
        )
    except (OSError, ValueError) as error:
        refusals.add(
            "selector_evidence_invalid",
            f"worker selector evidence did not validate: {error}",
            selector_profile=contract["selector_profile"],
        )

    resolved_partition: dict[str, Any] | None = None
    expected = contract["resolved_config"]
    try:
        resolved_partition = partition.analyze(
            server_log.read_text(encoding="utf-8", errors="replace"),
            expected_batched_tokens=int(expected["max_num_batched_tokens"]),
            expected_scheduled_tokens=int(expected["max_num_scheduled_tokens"]),
        )
    except (OSError, ValueError, KeyError) as error:
        refusals.add(
            "resolved_partition_invalid",
            f"resolved cache and partition settings did not prove out: {error}",
        )

    maps: list[dict[str, Any]] = []
    try:
        maps = load_map_evidence(map_evidence)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        refusals.add(
            "dso_evidence_invalid",
            f"grouped-GEMM map evidence did not load: {error}",
        )
    if maps:
        hashes = {record.get("sha256") for record in maps}
        refusals.require(
            len(hashes) == 1,
            "dso_hash_inconsistent",
            f"ranks mapped different grouped-GEMM DSOs: {sorted(hashes)}",
        )
        contracted = contract["build_identity"].get("grouped_gemm_dso_sha256")
        refusals.require(
            hashes == {contracted},
            "dso_hash_drift",
            "the mapped grouped-GEMM DSO is not the contracted one",
            contract=contracted,
            actual=sorted(hashes),
        )

    build = contract["build_identity"]
    refusals.require(
        build.get("vllm_commit") == vllm_commit,
        "vllm_commit_drift",
        "the declared vLLM commit is not the contracted one",
        contract=build.get("vllm_commit"),
        actual=vllm_commit,
    )
    refusals.require(
        build.get("kernels_commit") == kernels_commit,
        "kernels_commit_drift",
        "the declared XPU kernels commit is not the contracted one",
        contract=build.get("kernels_commit"),
        actual=kernels_commit,
    )

    sampling = contract["sampling"]
    refusals.require(
        float(sampling.get("temperature", 1.0)) == 0.0
        and float(sampling.get("top_p", 1.0)) == 1.0
        and sampling.get("ignore_eos") is False,
        "sampling_not_greedy",
        "the contract does not describe greedy decoding with natural stopping; "
        "exact regression detection is only valid under greedy sampling",
        sampling=sampling,
    )
    spec = expected.get("speculative") or {}
    refusals.require(
        spec.get("draft_sample_method") in (None, "greedy")
        and spec.get("rejection_sample_method") in (None, "standard"),
        "speculation_not_output_lossless",
        "speculative sampling is not greedy/standard, so accepted tokens are no "
        "longer guaranteed to equal the target argmax and exact comparison is "
        "not valid",
        speculative=spec,
    )
    refusals.require(
        int(expected.get("max_num_seqs", 0)) == 1,
        "batching_not_serial",
        "max_num_seqs is not one; concurrent requests change the verifier width "
        "and make outputs unreproducible",
        max_num_seqs=expected.get("max_num_seqs"),
    )

    return {
        "selector_profile": contract["selector_profile"],
        "worker_selector_records": resolved_selectors,
        "selector_contract_sha256": (
            resolved_selectors[0]["selector_contract_sha256"]
            if resolved_selectors
            else None
        ),
        "resolved_cache_partition": resolved_partition,
        "grouped_gemm_maps": maps,
        "vllm_commit": vllm_commit,
        "kernels_commit": kernels_commit,
        "model_identity": contract["model_identity"],
        "server_log_sha256": (
            sha256_bytes(server_log.read_bytes()) if server_log.is_file() else None
        ),
    }


def tokenizer_file_hashes(model_path: Path) -> dict[str, str]:
    names = (
        "config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "chat_template.jinja",
        "special_tokens_map.json",
        "generation_config.json",
    )
    return {
        name: sha256_bytes((model_path / name).read_bytes())
        for name in names
        if (model_path / name).is_file()
    }


# ---------------------------------------------------------------------------
# prompts
# ---------------------------------------------------------------------------


def as_ids(value: Any) -> list[int]:
    if isinstance(value, dict):
        value = value["input_ids"]
    elif hasattr(value, "input_ids"):
        value = value.input_ids
    if value and isinstance(value[0], list):
        value = value[0]
    return [int(token_id) for token_id in value]


def build_prompt_ids(tokenizer: Any, prompt_text: str) -> list[int]:
    """Apply the checkpoint's own chat template and return exact token IDs.

    Prompts are sent as token IDs, never as text, for the same reason the
    long-context gate does it: it removes the server-side templating and
    tokenization from the comparison, so a prompt hash means one exact array.
    """

    return as_ids(
        tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt_text}],
            tokenize=True,
            **CHAT_TEMPLATE_KWARGS,
        )
    )


# ---------------------------------------------------------------------------
# transport
# ---------------------------------------------------------------------------


def get_text(url: str, timeout: int) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def metric_value(metrics: str, name: str) -> float:
    pattern = re.compile(rf"^{re.escape(name)}(?:\{{[^}}]*\}})?\s+([^\s]+)$")
    return sum(
        float(match.group(1))
        for line in metrics.splitlines()
        if (match := pattern.match(line))
    )


METRIC_NAMES = (
    f"{PREFILL_TIME}_count",
    f"{DECODE_TIME}_count",
    SPEC_DRAFTS,
    SPEC_DRAFT_TOKENS,
    SPEC_ACCEPTED,
)


def metric_snapshot(base_url: str, timeout: int) -> dict[str, float]:
    metrics = get_text(f"{base_url.rstrip('/')}/metrics", timeout)
    return {name: metric_value(metrics, name) for name in METRIC_NAMES}


def post_stream(
    *,
    base_url: str,
    model: str,
    prompt_ids: list[int],
    max_tokens: int,
    sampling: dict[str, Any],
    timeout: int,
    request_id: str,
) -> dict[str, Any]:
    """One request, streamed, with token IDs returned.

    Streaming mirrors the long-context gate, which is the transport proven
    against this fork. ``ignore_eos`` is false here: an accuracy eval needs the
    model's natural stopping point, not a fixed-length window.
    """

    payload = {
        "model": model,
        "prompt": prompt_ids,
        "add_special_tokens": False,
        "truncate_prompt_tokens": None,
        "max_tokens": max_tokens,
        "temperature": sampling["temperature"],
        "top_p": sampling["top_p"],
        "seed": sampling.get("seed", 1),
        "ignore_eos": sampling["ignore_eos"],
        "stream": True,
        "stream_options": {"include_usage": True},
        "return_token_ids": True,
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-Request-Id": request_id},
        method="POST",
    )
    started = time.perf_counter()
    text_parts: list[str] = []
    token_ids: list[int] = []
    prompt_token_ids: list[int] | None = None
    usage: dict[str, Any] = {}
    finish_reason: str | None = None
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            for raw in response:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                body = line[5:].strip()
                if body == "[DONE]":
                    break
                event = json.loads(body)
                if event.get("usage"):
                    usage = event["usage"]
                for choice in event.get("choices", []):
                    if choice.get("finish_reason") is not None:
                        finish_reason = choice["finish_reason"]
                    returned = choice.get("prompt_token_ids")
                    if isinstance(returned, list):
                        prompt_token_ids = [int(value) for value in returned]
                    delta_ids = choice.get("token_ids")
                    if isinstance(delta_ids, list) and delta_ids:
                        token_ids.extend(int(value) for value in delta_ids)
                    if choice.get("text"):
                        text_parts.append(choice["text"])
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {error.code}: {body}") from error
    text = "".join(text_parts)
    return {
        "request_id": request_id,
        "elapsed_s": time.perf_counter() - started,
        "token_ids": token_ids,
        "prompt_token_ids_returned": prompt_token_ids,
        "usage": usage,
        "finish_reason": finish_reason,
        "text": text,
        "text_sha256": sha256_bytes(text.encode()),
    }


# ---------------------------------------------------------------------------
# per-request invariants
# ---------------------------------------------------------------------------


def request_checks(
    row: dict[str, Any], prompt_ids: list[int], deltas: dict[str, float]
) -> dict[str, bool]:
    usage = row.get("usage") or {}
    details = usage.get("prompt_tokens_details") or {}
    returned = row.get("prompt_token_ids_returned")
    return {
        "cache_zero": details.get("cached_tokens") == 0,
        "prompt_length_exact": usage.get("prompt_tokens") == len(prompt_ids),
        "returned_prompt_ids_exact": returned is None or returned == prompt_ids,
        "completion_length_agrees": usage.get("completion_tokens")
        == len(row["token_ids"]),
        "finish_reason_known": row.get("finish_reason") in ("stop", "length"),
        "prefill_metric_count_one": deltas[f"{PREFILL_TIME}_count"] == 1,
        "decode_metric_count_one": deltas[f"{DECODE_TIME}_count"] == 1,
    }


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------


def build_scorers(
    *,
    enable_code_execution: bool,
    policy: sandbox.SandboxPolicy,
    python_executable: str,
) -> dict[str, Callable[[datasets.EvalItem, str], dict[str, Any]]]:
    """Scorer table. The code-execution entry only exists when asked for."""

    table = dict(datasets.SCORERS)
    if enable_code_execution:

        def score_code_exec(item: datasets.EvalItem, completion: str) -> dict[str, Any]:
            program = datasets.build_code_program(item, completion)
            if program is None:
                return {
                    "scorer": datasets.CODE_EXEC_SCORER,
                    "correct": False,
                    "scoreable": False,
                    "reason": "no code block could be extracted from the response",
                }
            result = sandbox.run_untrusted_python(
                program, policy=policy, python_executable=python_executable
            )
            return {
                "scorer": datasets.CODE_EXEC_SCORER,
                "correct": result.passed,
                "scoreable": result.status != sandbox.STATUS_REFUSED,
                "program_sha256": sha256_bytes(program.encode()),
                "sandbox": result.as_record(),
            }

        table[datasets.CODE_EXEC_SCORER] = score_code_exec
    return table


def score_row(
    item: datasets.EvalItem,
    row: dict[str, Any],
    table: dict[str, Callable[[datasets.EvalItem, str], dict[str, Any]]],
) -> dict[str, Any]:
    """Score one response. A truncated or unscoreable item is never skipped."""

    truncated = row.get("finish_reason") == "length"
    scorer = table.get(item.scorer)
    if scorer is None:
        return {
            "scorer": item.scorer,
            "correct": False,
            "scoreable": False,
            "truncated": truncated,
            "reason": (
                f"scorer {item.scorer!r} is not enabled; code-execution scorers "
                "require --enable-code-execution"
            ),
        }
    result = scorer(item, row["text"])
    result["truncated"] = truncated
    if result.get("correct") is None:
        result["correct"] = False
        result["correct_is_undefined"] = True
    return result


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-dataset and overall counts. Every denominator is stated explicitly."""

    by_dataset: dict[str, dict[str, Any]] = {}
    for row in rows:
        bucket = by_dataset.setdefault(
            row["dataset"],
            {
                "items": 0,
                "correct": 0,
                "scoreable": 0,
                "unscoreable": 0,
                "truncated": 0,
                "correctness_defined": 0,
            },
        )
        score = row["score"]
        bucket["items"] += 1
        bucket["correct"] += int(bool(score.get("correct")))
        bucket["scoreable"] += int(bool(score.get("scoreable")))
        bucket["unscoreable"] += int(not score.get("scoreable"))
        bucket["truncated"] += int(bool(score.get("truncated")))
        bucket["correctness_defined"] += int(not score.get("correct_is_undefined"))
    for name, bucket in by_dataset.items():
        defined = bucket["correctness_defined"]
        bucket["dataset"] = name
        bucket["accuracy"] = bucket["correct"] / defined if defined else None
        bucket["accuracy_denominator"] = defined
        bucket["accuracy_note"] = (
            "correct / items with defined correctness. Unscoreable and "
            "truncated items count as incorrect, never as skipped."
        )
    totals = {
        "items": sum(bucket["items"] for bucket in by_dataset.values()),
        "correct": sum(bucket["correct"] for bucket in by_dataset.values()),
        "unscoreable": sum(bucket["unscoreable"] for bucket in by_dataset.values()),
        "truncated": sum(bucket["truncated"] for bucket in by_dataset.values()),
        "correctness_defined": sum(
            bucket["correctness_defined"] for bucket in by_dataset.values()
        ),
    }
    return {
        "by_dataset": dict(sorted(by_dataset.items())),
        "totals": totals,
    }


def determinism_summary(
    passes: list[dict[str, str]], replicates: int
) -> dict[str, Any]:
    """Compare the output token IDs of every pass, item by item.

    ``passes[i]`` maps ``item_id`` to that pass's output token-ID hash. A single
    mismatch means the configuration is not reproducible and no oracle may be
    minted from the run, regardless of what it scored.
    """

    if replicates < 2:
        return {
            "verified": False,
            "replicates": replicates,
            "reason": (
                "fewer than two passes were run; reproducibility was asserted, "
                "not measured"
            ),
            "divergent_items": [],
        }
    baseline = passes[0]
    divergent = sorted(
        item_id
        for item_id in baseline
        for other in passes[1:]
        if other.get(item_id) != baseline[item_id]
    )
    return {
        "verified": not divergent,
        "replicates": replicates,
        "reason": None if not divergent else "output token IDs differed across passes",
        "divergent_items": sorted(set(divergent)),
    }


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------


def load_all_datasets(
    contract: dict[str, Any], refusals: Refusals
) -> tuple[list[datasets.EvalItem], list[dict[str, Any]]]:
    items: list[datasets.EvalItem] = []
    provenance: list[dict[str, Any]] = []
    for entry in contract["datasets"]:
        try:
            loaded, record = datasets.load_items(
                entry["name"],
                Path(entry["path"]),
                expected_sha256=entry.get("sha256"),
                max_output_tokens=int(entry.get("max_output_tokens", 512)),
                limit=entry.get("limit"),
            )
        except datasets.DatasetUnavailable as error:
            refusals.add_record(error.as_refusal())
            continue
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
            refusals.add(
                "dataset_load_failed",
                f"{entry.get('name')}: {error}",
            )
            continue
        items.extend(loaded)
        provenance.append(record)
    if not items and not refusals:
        refusals.add("no_items", "the contract selected zero items")
    return items, provenance


def run_suite(
    *,
    items: list[datasets.EvalItem],
    prompt_ids: dict[str, list[int]],
    contract: dict[str, Any],
    replicates: int,
    timeout: int,
    scorer_table: dict[str, Callable[[datasets.EvalItem, str], dict[str, Any]]],
    send: Callable[..., dict[str, Any]],
    snapshot: Callable[[], dict[str, float]],
    refusals: Refusals,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Send every item, once per pass, strictly serially."""

    endpoint = contract["endpoint"]
    sampling = contract["sampling"]
    rows: list[dict[str, Any]] = []
    passes: list[dict[str, str]] = []
    for pass_index in range(replicates):
        pass_hashes: dict[str, str] = {}
        for order, item in enumerate(items):
            ids = prompt_ids[item.item_id]
            request_id = re.sub(
                r"[^A-Za-z0-9_.:-]",
                "-",
                f"laguna-acc-p{pass_index}-{order:04d}-{item.item_id}",
            )[:128]
            before = snapshot()
            try:
                row = send(
                    base_url=endpoint["base_url"],
                    model=endpoint["served_model_name"],
                    prompt_ids=ids,
                    max_tokens=item.max_output_tokens,
                    sampling=sampling,
                    timeout=timeout,
                    request_id=request_id,
                )
            except (RuntimeError, OSError, urllib.error.URLError) as error:
                refusals.add(
                    "request_failed",
                    f"{item.item_id} pass {pass_index}: {error}",
                    item_id=item.item_id,
                    pass_index=pass_index,
                )
                continue
            after = snapshot()
            if before.keys() != after.keys():
                refusals.add(
                    "metric_schema_drift",
                    f"{item.item_id} pass {pass_index}: metric key set changed",
                )
                continue
            deltas = {name: after[name] - before[name] for name in before}
            checks = request_checks(row, ids, deltas)
            output_hash = token_hash(row["token_ids"])
            pass_hashes[item.item_id] = output_hash
            record = {
                "item_id": item.item_id,
                "dataset": item.dataset,
                "row_id": item.row_id,
                "pass_index": pass_index,
                "order": order,
                "prompt_sha256": item.prompt_sha256,
                "prompt_token_ids_sha256": token_hash(ids),
                "prompt_token_count": len(ids),
                "max_output_tokens": item.max_output_tokens,
                "output_token_ids_sha256": output_hash,
                "output_token_count": len(row["token_ids"]),
                "text_sha256": row["text_sha256"],
                "text": row["text"],
                "finish_reason": row.get("finish_reason"),
                "usage": row.get("usage"),
                "prometheus_delta": deltas,
                "checks": checks,
                "checks_passed": all(checks.values()),
            }
            if pass_index == 0:
                record["score"] = score_row(item, row, scorer_table)
            rows.append(record)
            if not record["checks_passed"]:
                failed = sorted(name for name, ok in checks.items() if not ok)
                refusals.add(
                    "request_invariant_failed",
                    f"{item.item_id} pass {pass_index} failed: {', '.join(failed)}",
                    item_id=item.item_id,
                    pass_index=pass_index,
                    failed_checks=failed,
                )
        missing = [item.item_id for item in items if item.item_id not in pass_hashes]
        if missing:
            refusals.add(
                "items_missing_from_pass",
                f"pass {pass_index} produced no response for {len(missing)} item(s)",
                pass_index=pass_index,
                item_ids=sorted(missing)[:20],
            )
        passes.append(pass_hashes)
    return rows, passes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--server-log", type=Path)
    parser.add_argument("--map-evidence", type=Path)
    parser.add_argument("--vllm-commit")
    parser.add_argument("--kernels-commit")
    parser.add_argument("--replicates", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--enable-code-execution", action="store_true")
    parser.add_argument(
        "--sandbox-network-namespace",
        action="store_true",
        help="require unshare -n -r around every executed program",
    )
    parser.add_argument("--sandbox-timeout-s", type=float, default=10.0)
    parser.add_argument("--sandbox-python", default=sys.executable)
    parser.add_argument(
        "--build-only",
        action="store_true",
        help="resolve datasets, prompts and revisions; contact nothing",
    )
    return parser


def load_tokenizer(model_path: Path) -> Any:
    """Load the served checkpoint's own tokenizer.

    Imported lazily and injectable through :func:`main` so every unit test can
    run with a stub: the harness must be fully exercisable with no model, no
    device, and no network.
    """

    from transformers import AutoTokenizer  # noqa: PLC0415 - keep the import lazy

    return AutoTokenizer.from_pretrained(
        model_path, local_files_only=True, fix_mistral_regex=True
    )


def main(argv: list[str] | None = None, *, tokenizer: Any | None = None) -> int:
    args = build_parser().parse_args(argv)
    refusals = Refusals()
    contract = load_contract(args.contract)
    revisions = check_revisions(contract, refusals)
    items, dataset_provenance = load_all_datasets(contract, refusals)

    code_items = [item for item in items if item.scorer == datasets.CODE_EXEC_SCORER]
    if code_items and not args.enable_code_execution:
        refusals.add(
            "code_execution_not_enabled",
            f"{len(code_items)} item(s) require executing model-written code; "
            "pass --enable-code-execution to allow it",
            datasets=sorted({item.dataset for item in code_items}),
        )

    policy = sandbox.SandboxPolicy(
        timeout_s=args.sandbox_timeout_s,
        use_network_namespace=args.sandbox_network_namespace,
    )
    scorer_table = build_scorers(
        enable_code_execution=args.enable_code_execution,
        policy=policy,
        python_executable=args.sandbox_python,
    )

    if tokenizer is None:
        tokenizer = load_tokenizer(args.model_path)
    prompt_ids = {
        item.item_id: build_prompt_ids(tokenizer, item.prompt_text) for item in items
    }
    tokenizer_hashes = tokenizer_file_hashes(args.model_path)
    contracted_tokenizer = (
        contract["model_identity"].get("tokenizer_files_sha256") or {}
    )
    for name, expected in sorted(contracted_tokenizer.items()):
        refusals.require(
            tokenizer_hashes.get(name) == expected,
            "tokenizer_drift",
            f"{name} does not match the contracted checkpoint",
            contract=expected,
            actual=tokenizer_hashes.get(name),
        )

    base_result: dict[str, Any] = {
        "schema": SCHEMA,
        "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
        "contract": {
            "path": str(args.contract),
            "sha256": sha256_bytes(args.contract.read_bytes()),
            "contract_id": contract["contract_id"],
            "selector_profile": contract["selector_profile"],
        },
        "revisions": revisions,
        "datasets": dataset_provenance,
        "model_path": str(args.model_path),
        "tokenizer_files_sha256": tokenizer_hashes,
        "chat_template_kwargs": CHAT_TEMPLATE_KWARGS,
        "sampling": contract["sampling"],
        "replicates": args.replicates,
        "code_execution_enabled": args.enable_code_execution,
        "sandbox_policy": policy.as_record() if args.enable_code_execution else None,
        "prompt_manifest": [
            {
                "item_id": item.item_id,
                "dataset": item.dataset,
                "scorer": item.scorer,
                "prompt_sha256": item.prompt_sha256,
                "prompt_token_ids_sha256": token_hash(prompt_ids[item.item_id]),
                "prompt_token_count": len(prompt_ids[item.item_id]),
                "max_output_tokens": item.max_output_tokens,
            }
            for item in items
        ],
    }

    if args.build_only:
        base_result.update(
            {
                "status": "BUILD_ONLY",
                "refusals": refusals.entries,
                "rows": [],
            }
        )
        write_result(args.out, base_result)
        print(json.dumps({"status": "BUILD_ONLY", "items": len(items)}))
        return 0

    for name in ("server_log", "map_evidence", "vllm_commit", "kernels_commit"):
        if getattr(args, name) is None:
            refusals.add(
                "attribution_argument_missing",
                f"--{name.replace('_', '-')} is required for a scoring run",
            )
    if not refusals:
        base_result["attribution"] = collect_attribution(
            contract,
            server_log=args.server_log,
            map_evidence=args.map_evidence,
            vllm_commit=args.vllm_commit,
            kernels_commit=args.kernels_commit,
            refusals=refusals,
        )

    if refusals:
        base_result.update(
            {"status": STATUS_REFUSED, "refusals": refusals.entries, "rows": []}
        )
        write_result(args.out, base_result)
        print(
            json.dumps(
                {"status": STATUS_REFUSED, "refusals": len(refusals)}, sort_keys=True
            )
        )
        return 2

    rows, passes = run_suite(
        items=items,
        prompt_ids=prompt_ids,
        contract=contract,
        replicates=max(1, args.replicates),
        timeout=args.timeout,
        scorer_table=scorer_table,
        send=post_stream,
        snapshot=lambda: metric_snapshot(
            contract["endpoint"]["base_url"], args.timeout
        ),
        refusals=refusals,
    )
    scored = [row for row in rows if row["pass_index"] == 0]
    determinism = determinism_summary(passes, max(1, args.replicates))
    summary = aggregate(scored)
    summary["determinism"] = determinism

    if refusals:
        status = STATUS_REFUSED
    elif determinism["verified"]:
        status = STATUS_PASS
    else:
        status = STATUS_PASS_UNVERIFIED

    base_result.update(
        {
            "status": status,
            "refusals": refusals.entries,
            "summary": summary,
            "rows": rows,
        }
    )
    write_result(args.out, base_result)
    print(json.dumps({"status": status, "summary": summary}, sort_keys=True))
    return 0 if status != STATUS_REFUSED else 2


def write_result(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
