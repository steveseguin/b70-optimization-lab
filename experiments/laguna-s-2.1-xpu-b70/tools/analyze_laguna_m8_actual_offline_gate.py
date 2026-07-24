#!/usr/bin/env python3
"""Fail-closed parser and A/B/C comparator for Laguna M=8 raw evidence.

The runtime recorder writes one ``rankXX-pid*-evidenceNNNN`` directory for
each eligible target forward.  This module deliberately consumes those low
level manifests first, validates every referenced byte file, and only then
constructs the compact aggregate used for cross-arm comparison.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
from pathlib import Path
from typing import Any


FORMAT = "laguna-m8-raw-evidence-v1"
RECORDER_MARKER = "LAGUNA_M8_RAW_EVIDENCE_V1"
SCHEMA = "laguna-m8-actual-offline-gate-v2"
DRIVER_SCHEMA = "laguna-m8-offline-arm-v1"
ARMS = ("incumbent-eager", "segmented-eager", "segmented-graph")
RANKS = range(4)
MIN_EVENTS_PER_RANK = 4
COLLECTIVE_COUNT = 97
GRAPH_COUNTS = {"graphs": 146, "eager_breaks": 145}
TARGET_REVISION = "4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb"
DRAFT_REVISION = "5e07c246915c86dc6920fead03d019989224f2ba"
VLLM_COMMIT = "5c6c108bf152f985e126db9d77897ae442b75048"
MAX_TOKENS = 32
SEED = 1
PROMPT_SHA256 = "2ea384ff8e947b67345541471c400e77f82e308ef8a66305c8f49e97ee2b172f"
ABSENT_ENVIRONMENT = [
    "TRITON_INTEL_DISABLE_IGC_OPT",
    "VLLM_LAGUNA_TARGET_TRACE",
    "VLLM_LAGUNA_TARGET_TRACE_DIR",
    "VLLM_LAGUNA_TARGET_TRACE_INPUTS",
    "VLLM_LAGUNA_TARGET_TRACE_LAYER",
    "VLLM_LAGUNA_TARGET_TRACE_POSITION",
    "VLLM_LAGUNA_TARGET_TRACE_RANK",
    "VLLM_XPU_LAGUNA_PARITY_RETURN_STAGE",
]
_RUN_DIR_RE = re.compile(r"rank(?P<rank>\d{2})-pid\d+-evidence(?P<sequence>\d{4})")


def die(message: str) -> None:
    raise ValueError(message)


def digest_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        path_stat = path.lstat()
    except OSError as exc:
        die(f"cannot stat {path}: {exc}")
    if path.is_symlink() or not stat.S_ISREG(path_stat.st_mode):
        die(f"{path}: expected a regular, non-symlink JSON file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        die(f"cannot read {path}: {exc}")
    if not isinstance(value, dict):
        die(f"{path}: expected JSON object")
    return value


def _signature_identity(
    signature: Any, context: str
) -> tuple[str, int, str, tuple[int, ...], tuple[int, ...], str]:
    required = {"device", "dtype", "nbytes", "sha256", "shape", "stride"}
    if not isinstance(signature, dict) or set(signature) != required:
        die(f"{context}: tensor signature fields drift")
    sha = signature["sha256"]
    nbytes = signature["nbytes"]
    shape = signature["shape"]
    stride = signature["stride"]
    if (
        not isinstance(sha, str)
        or len(sha) != 64
        or any(ch not in "0123456789abcdef" for ch in sha)
        or not isinstance(nbytes, int)
        or nbytes <= 0
        or not isinstance(signature["dtype"], str)
        or not signature["dtype"].startswith("torch.")
        or not isinstance(signature["device"], str)
        or not signature["device"].startswith("xpu:")
        or not isinstance(shape, list)
        or not shape
        or not all(isinstance(item, int) and item >= 0 for item in shape)
        or not isinstance(stride, list)
        or len(stride) != len(shape)
        or not all(isinstance(item, int) and item >= 0 for item in stride)
    ):
        die(f"{context}: invalid tensor signature")
    return (
        sha,
        nbytes,
        signature["dtype"],
        tuple(shape),
        tuple(stride),
        signature["device"],
    )


def _raw_identity(
    run_dir: Path, event: dict[str, Any], context: str
) -> tuple[str, int, str, tuple[int, ...], tuple[int, ...], str]:
    details = event.get("details")
    output = details.get("output") if isinstance(details, dict) else None
    raw_name = event.get("raw_file")
    if not isinstance(output, dict) or not isinstance(raw_name, str):
        die(f"{context}: tensor record lacks output/raw_file")
    identity = _signature_identity(output, f"{context}:output")
    sha, nbytes = identity[:2]
    expected_name = f"events/{event['event_index']:05d}-{event['label']}.bin"
    raw_entry = run_dir / raw_name
    raw_path = raw_entry.resolve(strict=False)
    root = run_dir.resolve()
    if (
        raw_name != expected_name
        or root not in raw_path.parents
        or raw_entry.is_symlink()
        or not raw_path.is_file()
        or not stat.S_ISREG(raw_path.lstat().st_mode)
    ):
        die(f"{context}: invalid raw output identity")
    data = raw_path.read_bytes()
    if len(data) != nbytes or hashlib.sha256(data).hexdigest() != sha:
        die(f"{context}: raw output bytes do not match manifest")
    return identity


def _tensor_input_signature(
    event: dict[str, Any], name: str, context: str
) -> tuple[str, int, str, tuple[int, ...], tuple[int, ...], str]:
    details = event.get("details")
    inputs = details.get("input_signatures") if isinstance(details, dict) else None
    signature = inputs.get(name) if isinstance(inputs, dict) else None
    if not isinstance(inputs, dict) or set(inputs) != {name}:
        die(f"{context}: missing input signature {name}")
    return _signature_identity(signature, f"{context}:input:{name}")


def _hidden_input_signatures(
    event: dict[str, Any], context: str
) -> tuple[
    tuple[str, int, str, tuple[int, ...], tuple[int, ...], str],
    tuple[str, int, str, tuple[int, ...], tuple[int, ...], str],
    tuple[str, int, str, tuple[int, ...], tuple[int, ...], str],
]:
    details = event.get("details")
    inputs = details.get("input_signatures") if isinstance(details, dict) else None
    expected = {"input_ids", "positions", "slot_mapping"}
    if not isinstance(inputs, dict) or set(inputs) != expected:
        die(f"{context}: hidden input signature fields drift")
    return tuple(
        _signature_identity(inputs[name], f"{context}:input:{name}")
        for name in ("input_ids", "positions", "slot_mapping")
    )


def _single(events: list[dict[str, Any]], label: str, context: str) -> dict[str, Any]:
    matches = [event for event in events if event.get("label") == label]
    if len(matches) != 1:
        die(f"{context}: expected exactly one {label}, found {len(matches)}")
    return matches[0]


def _metadata(event: dict[str, Any], label: str, context: str) -> dict[str, Any]:
    if "raw_file" in event or not isinstance(event.get("details"), dict):
        die(f"{context}: {label} must be metadata only")
    return event["details"]


def _token_ids(value: Any, context: str) -> tuple[int, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, int) and not isinstance(item, bool) for item in value
    ):
        die(f"{context}: token IDs must be a flat integer list")
    return tuple(value)


def _bookkeeping_token_ids(value: Any, context: str) -> tuple[int, ...]:
    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], list):
        return _token_ids(value[0], context)
    return _token_ids(value, context)


def _expected_boundaries() -> list[str]:
    result = ["embedding_reduce"]
    for layer in range(48):
        result.extend(
            (f"attention:{layer}", f"gather:{2 * layer}", f"gather:{2 * layer + 1}")
        )
    return result


def _expected_labels(arm: str, graph_phase: str | None = None) -> list[str]:
    labels = ["logical_event_key", "phase", "arm_contract"]
    if arm == "segmented-graph":
        if graph_phase not in {"capture", "replay"}:
            die("internal graph phase is missing")
        labels.append("phase")
    if arm != "incumbent-eager":
        labels.extend(("boundary", "embedding_all_reduce"))
        for layer in range(48):
            labels.append("boundary")
            labels.extend(
                f"attention_{layer:02d}_{suffix}"
                for suffix in ("query", "key", "value", "output")
            )
            labels.extend(("boundary", "all_gather", "boundary", "all_gather"))
        labels.append("full_topology")
    else:
        for layer in range(48):
            labels.extend(
                f"attention_{layer:02d}_{suffix}"
                for suffix in ("query", "key", "value", "output")
            )
    if arm == "segmented-graph":
        labels.append(f"breakable_{graph_phase}_topology")
    labels.extend(
        (
            "target_hidden_before_logits",
            "kv_capture_status",
            "logits_boundary",
            "sampled_token_ids_after_logits",
            "spec_acceptance_before_bookkeeping",
            "emitted_ids_after_bookkeeping",
        )
    )
    return labels


def _validate_logical_key(
    value: dict[str, Any], rank: int, context: str
) -> dict[str, Any]:
    required = {
        "candidate_ids",
        "positions",
        "rank",
        "request_generation_epoch",
        "seq_query_metadata",
        "slot_mapping_sha256",
        "target_ordinal",
    }
    if set(value) != required or value["rank"] != rank:
        die(f"{context}: logical event key fields/rank drift")
    if (
        not isinstance(value["candidate_ids"], list)
        or not isinstance(value["positions"], list)
        or len(value["candidate_ids"]) != 8
        or len(value["positions"]) != 8
        or not all(
            isinstance(item, int)
            for item in value["candidate_ids"] + value["positions"]
        )
        or not isinstance(value["request_generation_epoch"], int)
        or value["request_generation_epoch"] < 0
        or not isinstance(value["target_ordinal"], int)
        or value["target_ordinal"] < 0
        or not isinstance(value["slot_mapping_sha256"], str)
        or len(value["slot_mapping_sha256"]) != 64
        or any(ch not in "0123456789abcdef" for ch in value["slot_mapping_sha256"])
    ):
        die(f"{context}: logical event key is not canonical M=8")
    metadata = value["seq_query_metadata"]
    expected_metadata = {
        "num_reqs",
        "num_tokens_padded",
        "num_tokens_unpadded",
        "query_len",
    }
    if (
        not isinstance(metadata, dict)
        or set(metadata) != expected_metadata
        or metadata["num_reqs"] != 1
        or metadata["num_tokens_unpadded"] != 8
        or metadata["query_len"] != 8
        or not isinstance(metadata["num_tokens_padded"], int)
        or metadata["num_tokens_padded"] < 8
    ):
        die(f"{context}: sequence/query metadata drift")
    return value


def _validate_event(
    run_dir: Path, arm: str, rank: int, manifest: dict[str, Any]
) -> dict[str, Any]:
    context = str(run_dir)
    expected_manifest_fields = {
        "arm",
        "event_count",
        "events",
        "format",
        "marker",
        "rank",
    }
    if (
        set(manifest) != expected_manifest_fields
        or manifest.get("format") != FORMAT
        or manifest.get("marker") != RECORDER_MARKER
        or manifest.get("arm") != arm
        or manifest.get("rank") != rank
    ):
        die(f"{context}: recorder format/arm/rank mismatch")
    events = manifest.get("events")
    if not isinstance(events, list) or manifest.get("event_count") != len(events):
        die(f"{context}: manifest event count mismatch")
    for index, event in enumerate(events):
        if (
            not isinstance(event, dict)
            or set(event)
            not in (
                {
                    "details",
                    "event_index",
                    "label",
                    "logical_event_key",
                    "phase",
                    "rank",
                },
                {
                    "details",
                    "event_index",
                    "label",
                    "logical_event_key",
                    "phase",
                    "rank",
                    "raw_file",
                },
            )
            or event.get("event_index") != index
            or event.get("rank") != rank
        ):
            die(f"{context}: noncanonical event index/rank")
        if not isinstance(event.get("label"), str) or not isinstance(
            event.get("phase"), str
        ):
            die(f"{context}: event lacks label/phase")

    logical = _validate_logical_key(
        _metadata(
            _single(events, "logical_event_key", context), "logical_event_key", context
        ),
        rank,
        context,
    )
    if any(event.get("logical_event_key") != logical for event in events):
        die(f"{context}: per-event logical key drift")
    phase_records = [
        _metadata(event, "phase", context)
        for event in events
        if event.get("label") == "phase"
    ]
    expected_phases = (
        ["segmented-eager"] if arm == "segmented-eager" else ["incumbent-eager"]
    )
    if arm == "segmented-graph":
        expected_phases.append(
            "capture"
            if any(
                event.get("label") == "breakable_capture_topology" for event in events
            )
            else "replay"
        )
    if [item.get("phase") for item in phase_records] != expected_phases:
        die(f"{context}: phase sequence drift")
    labels = [event["label"] for event in events]
    if labels != _expected_labels(
        arm, expected_phases[-1] if arm == "segmented-graph" else None
    ):
        die(f"{context}: low-level label order drift")
    base_phase = expected_phases[0]
    graph_phase = expected_phases[-1]
    expected_event_phases = ["uninitialized", base_phase, base_phase]
    if arm == "segmented-graph":
        expected_event_phases.append(graph_phase)
    expected_event_phases.extend(
        [graph_phase] * (len(events) - len(expected_event_phases))
    )
    if [event["phase"] for event in events] != expected_event_phases:
        die(f"{context}: per-event phase drift")
    events_dir = run_dir / "events"
    expected_event_files: set[str] = set()
    for event in events:
        sidecar = events_dir / f"{event['event_index']:05d}-{event['label']}.json"
        expected_event_files.add(sidecar.name)
        if load_json(sidecar) != event:
            die(f"{context}: event sidecar differs from manifest")
        if "raw_file" in event:
            expected_event_files.add(Path(event["raw_file"]).name)
    if (
        not events_dir.is_dir()
        or events_dir.is_symlink()
        or {item.name for item in events_dir.iterdir()} != expected_event_files
    ):
        die(f"{context}: recorder event file set drift")
    contract = _metadata(
        _single(events, "arm_contract", context), "arm_contract", context
    )
    expected_contract = {
        "drafter_is_breakable": False,
        "logits_outside_model_wrapper": True,
        "target_is_breakable": arm == "segmented-graph",
    }
    if contract != expected_contract:
        die(f"{context}: target/drafter arm isolation drift")

    boundary_labels = [
        event["details"].get("boundary")
        for event in events
        if event["label"] == "boundary"
    ]
    collective_events = [
        event
        for event in events
        if event["label"] in ("embedding_all_reduce", "all_gather")
    ]
    if arm == "incumbent-eager":
        if boundary_labels or collective_events or "full_topology" in labels:
            die(f"{context}: incumbent arm emitted segmented topology")
        collectives: tuple[Any, ...] = ()
    else:
        if boundary_labels != _expected_boundaries():
            die(f"{context}: 145 boundary labels/order drift")
        if (
            len(collective_events) != COLLECTIVE_COUNT
            or collective_events[0].get("label") != "embedding_all_reduce"
        ):
            die(f"{context}: 97 collective labels/order drift")
        collectives_list: list[tuple[Any, ...]] = []
        for index, event in enumerate(collective_events):
            details = event["details"]
            expected_label = "embedding_all_reduce" if index == 0 else "all_gather"
            expected_index = None if index == 0 else index - 1
            if (
                set(details)
                != {
                    "collective_index",
                    "input_signatures",
                    "output",
                }
                or event["label"] != expected_label
                or details.get("collective_index") != expected_index
            ):
                die(f"{context}: collective ordinal drift at {index}")
            collectives_list.append(
                (
                    event["label"],
                    expected_index,
                    _raw_identity(run_dir, event, f"{context}:collective[{index}]"),
                    _tensor_input_signature(
                        event, "local_input", f"{context}:collective[{index}]"
                    ),
                )
            )
        topology = _metadata(
            _single(events, "full_topology", context), "full_topology", context
        )
        if topology != {"boundary_count": 145, "collective_count": 97}:
            die(f"{context}: full topology summary drift")
        collectives = tuple(collectives_list)

    attention: list[tuple[tuple[Any, ...], ...]] = []
    for layer in range(48):
        values: list[tuple[Any, ...]] = []
        for suffix in ("query", "key", "value", "output"):
            event = _single(events, f"attention_{layer:02d}_{suffix}", context)
            if set(event["details"]) != {"input_signatures", "output"}:
                die(f"{context}: attention details drift at layer {layer} {suffix}")
            raw = _raw_identity(
                run_dir, event, f"{context}:attention[{layer}]:{suffix}"
            )
            slot = _tensor_input_signature(
                event,
                "slot_mapping",
                f"{context}:attention[{layer}]:{suffix}",
            )
            if slot[0] != logical["slot_mapping_sha256"]:
                die(f"{context}: attention slot mapping differs from logical key")
            values.append((raw, slot))
        attention.append(tuple(values))
    hidden_event = _single(events, "target_hidden_before_logits", context)
    if set(hidden_event["details"]) != {"input_signatures", "output"}:
        die(f"{context}: target hidden details drift")
    hidden_inputs = _hidden_input_signatures(hidden_event, f"{context}:hidden")
    if hidden_inputs[2][0] != logical["slot_mapping_sha256"]:
        die(f"{context}: hidden slot mapping differs from logical key")
    hidden = (
        _raw_identity(run_dir, hidden_event, f"{context}:hidden"),
        hidden_inputs,
    )
    sampled_event = _single(events, "sampled_token_ids_after_logits", context)
    if sampled_event["details"].get("input_signatures") != {} or set(
        sampled_event["details"]
    ) != {"input_signatures", "output"}:
        die(f"{context}: sampled-token details drift")
    sampled = _raw_identity(run_dir, sampled_event, f"{context}:sampled")
    kv = _metadata(
        _single(events, "kv_capture_status", context), "kv_capture_status", context
    )
    if (
        set(kv) != {"physical_kv_cache_bytes_supported", "status", "reason"}
        or kv["physical_kv_cache_bytes_supported"] is not False
        or kv["status"] != "unsupported"
        or not isinstance(kv["reason"], str)
    ):
        die(f"{context}: physical KV must be explicitly unsupported")
    if _metadata(
        _single(events, "logits_boundary", context), "logits_boundary", context
    ) != {"after_target_model_forward": True}:
        die(f"{context}: logits boundary drift")
    acceptance = _metadata(
        _single(events, "spec_acceptance_before_bookkeeping", context),
        "spec_acceptance_before_bookkeeping",
        context,
    )
    if set(acceptance) != {
        "accepted_draft_count",
        "emitted_ids_before_bookkeeping",
        "first_rejected_draft_index",
        "proposed_draft_ids",
    }:
        die(f"{context}: speculative acceptance structure drift")
    proposed = _token_ids(
        acceptance["proposed_draft_ids"], f"{context}:proposed drafts"
    )
    emitted_before = _token_ids(
        acceptance["emitted_ids_before_bookkeeping"],
        f"{context}:pre-bookkeeping emitted IDs",
    )
    accepted = acceptance["accepted_draft_count"]
    if (
        len(proposed) != 7
        or not isinstance(accepted, int)
        or isinstance(accepted, bool)
        or not 0 <= accepted <= 7
        or not 1 <= len(emitted_before) <= 8
    ):
        die(f"{context}: speculative acceptance dimensions drift")
    prefix = 0
    for proposed_id, emitted_id in zip(proposed, emitted_before, strict=False):
        if proposed_id != emitted_id:
            break
        prefix += 1
    expected_rejected = None if prefix == 7 else prefix
    if (
        accepted != prefix
        or acceptance["first_rejected_draft_index"] != expected_rejected
    ):
        die(f"{context}: speculative accepted-prefix metadata is inconsistent")
    bookkeeping = _metadata(
        _single(events, "emitted_ids_after_bookkeeping", context),
        "emitted_ids_after_bookkeeping",
        context,
    )
    if set(bookkeeping) != {"emitted_ids"}:
        die(f"{context}: emitted-id bookkeeping structure drift")
    emitted_after = _bookkeeping_token_ids(
        bookkeeping["emitted_ids"], f"{context}:post-bookkeeping emitted IDs"
    )
    if emitted_after != emitted_before:
        die(f"{context}: bookkeeping changed emitted token IDs")
    normalized_acceptance = {
        "accepted_draft_count": accepted,
        "emitted_ids_before_bookkeeping": emitted_before,
        "first_rejected_draft_index": expected_rejected,
        "proposed_draft_ids": proposed,
    }

    graph: dict[str, Any] | None = None
    if arm == "segmented-graph":
        capture = [
            event for event in events if event["label"] == "breakable_capture_topology"
        ]
        replay = [
            event for event in events if event["label"] == "breakable_replay_topology"
        ]
        if len(capture) + len(replay) != 1:
            die(f"{context}: graph event must be exactly one capture or replay")
        graph = _metadata(
            (capture or replay)[0], (capture or replay)[0]["label"], context
        )
        expected_graph_fields = {
            "capture_count",
            "descriptor",
            "eager_breaks",
            "graphs",
            ("ordered_boundary_categories" if capture else "replay_count"),
        }
        if (
            set(graph) != expected_graph_fields
            or graph.get("graphs") != GRAPH_COUNTS["graphs"]
            or graph.get("eager_breaks") != GRAPH_COUNTS["eager_breaks"]
            or not isinstance(graph.get("descriptor"), str)
            or not graph["descriptor"]
        ):
            die(f"{context}: graph counts/descriptor drift")
        if capture and (
            graph.get("capture_count") != 1
            or graph.get("ordered_boundary_categories")
            != {"attention": 48, "collective": 97}
        ):
            die(f"{context}: capture provenance drift")
        if replay and (
            graph.get("capture_count") != 1
            or not isinstance(graph.get("replay_count"), int)
            or graph["replay_count"] < 1
        ):
            die(f"{context}: replay provenance drift")
    elif any(label.startswith("breakable_") for label in labels):
        die(f"{context}: eager arm emitted graph provenance")

    return {
        "logical_key": logical,
        "phase": expected_phases[-1],
        "attention": tuple(attention),
        "target_hidden": hidden,
        "sampled_token_ids": sampled,
        "acceptance": normalized_acceptance,
        "emitted_ids": emitted_after,
        "physical_kv": kv,
        "collectives": collectives,
        "graph": graph,
    }


def aggregate_recorder_root(arm: str, evidence_root: Path) -> dict[str, Any]:
    """Validate rank-local recorder directories and return path-free evidence."""
    if arm not in ARMS or not evidence_root.is_dir() or evidence_root.is_symlink():
        die(f"{evidence_root}: invalid arm or absent recorder root")
    discovered: dict[int, list[tuple[int, Path]]] = {rank: [] for rank in RANKS}
    for item in evidence_root.iterdir():
        if item.name == "evidence.json" and item.is_file() and not item.is_symlink():
            continue
        match = _RUN_DIR_RE.fullmatch(item.name)
        if not item.is_dir() or item.is_symlink() or match is None:
            die(f"{evidence_root}: unexpected recorder entry {item.name!r}")
        rank, sequence = int(match["rank"]), int(match["sequence"])
        if rank not in RANKS:
            die(f"{item}: rank outside 0..3")
        discovered[rank].append((sequence, item))
    if any(not items for items in discovered.values()):
        die(f"{evidence_root}: exactly four rank recorder streams are required")
    rank_events: dict[str, list[dict[str, Any]]] = {}
    for rank, items in discovered.items():
        ordered = sorted(items)
        sequences = [sequence for sequence, _ in ordered]
        if sequences != list(range(1, len(ordered) + 1)):
            die(f"{evidence_root}: rank {rank} recorder sequences are not contiguous")
        parsed = [
            _validate_event(path, arm, rank, load_json(path / "manifest.json"))
            for _, path in ordered
        ]
        if len(parsed) < MIN_EVENTS_PER_RANK:
            die(
                f"{evidence_root}: rank {rank} has fewer than {MIN_EVENTS_PER_RANK} eligible events"
            )
        epochs = [event["logical_key"]["request_generation_epoch"] for event in parsed]
        if any(later <= earlier for earlier, later in zip(epochs, epochs[1:])):
            die(
                f"{evidence_root}: rank {rank} request generation epochs are not strictly increasing"
            )
        rank_events[str(rank)] = parsed
    counts = {len(events) for events in rank_events.values()}
    if len(counts) != 1:
        die(f"{evidence_root}: ranks disagree on eligible-event count")
    if arm == "segmented-graph":
        for rank, events in rank_events.items():
            if events[0]["phase"] != "capture" or any(
                event["phase"] != "replay" for event in events[1:]
            ):
                die(
                    f"{evidence_root}: rank {rank} must capture once then replay every later graph event"
                )
            descriptors = {event["graph"]["descriptor"] for event in events}
            if len(descriptors) != 1:
                die(f"{evidence_root}: rank {rank} graph descriptor drift")
            for ordinal, event in enumerate(events):
                graph = event["graph"]
                if graph["capture_count"] != 1:
                    die(f"{evidence_root}: rank {rank} graph recapture detected")
                if ordinal == 0:
                    if "replay_count" in graph:
                        die(f"{evidence_root}: rank {rank} capture has replay count")
                elif graph.get("replay_count") != ordinal:
                    die(f"{evidence_root}: rank {rank} replay counter drift")
    elif any(
        event["phase"] != arm for events in rank_events.values() for event in events
    ):
        die(f"{evidence_root}: eager phase drift")
    aggregate = {
        "schema": SCHEMA,
        "format": FORMAT,
        "arm": arm,
        "rank_events": rank_events,
    }
    return json.loads(json.dumps(aggregate, sort_keys=True))


def normalize_evidence(arm: str, path: Path, evidence_root: Path) -> dict[str, Any]:
    data = load_json(path)
    if (
        set(data) != {"arm", "format", "rank_events", "schema"}
        or data.get("schema") != SCHEMA
        or data.get("format") != FORMAT
        or data.get("arm") != arm
    ):
        die(f"{path}: wrong aggregate schema/format/arm")
    events = data.get("rank_events")
    if not isinstance(events, dict) or set(events) != {str(rank) for rank in RANKS}:
        die(f"{path}: aggregate must contain exactly four rank event streams")
    if any(
        not isinstance(events[str(rank)], list)
        or len(events[str(rank)]) < MIN_EVENTS_PER_RANK
        for rank in RANKS
    ):
        die(f"{path}: incomplete rank event stream")
    recomputed = aggregate_recorder_root(arm, evidence_root)
    if data != recomputed:
        die(f"{path}: stored aggregate differs from revalidated raw evidence")
    return recomputed


def compare(left: dict[str, Any], right: dict[str, Any], label: str) -> None:
    for rank in map(str, RANKS):
        left_events, right_events = (
            left["rank_events"][rank],
            right["rank_events"][rank],
        )
        if len(left_events) != len(right_events):
            die(f"{label}: rank {rank} missing/extra eligible event")
        for ordinal, (a, b) in enumerate(zip(left_events, right_events, strict=True)):
            for field in (
                "logical_key",
                "acceptance",
                "emitted_ids",
                "target_hidden",
                "sampled_token_ids",
                "attention",
                "physical_kv",
            ):
                if a[field] != b[field]:
                    die(f"{label}: rank {rank} event {ordinal} {field} differs")


def _validate_driver(
    arm: str, arm_root: Path, driver: dict[str, Any]
) -> tuple[int, ...]:
    required_fields = {
        "absent_environment",
        "arm",
        "compilation_config",
        "draft_model",
        "draft_revision",
        "engine_config",
        "environment",
        "evidence_dir",
        "finish_reason",
        "generation_config",
        "ignore_eos",
        "max_tokens",
        "model",
        "model_manifest_sha256",
        "nonbenchmark",
        "num_cached_tokens",
        "offline_only",
        "prompt_sha256",
        "runtime",
        "schema",
        "seed",
        "single_generate_call",
        "speculative_config",
        "text_sha256",
        "target_revision",
        "token_ids",
        "token_ids_sha256",
        "usage",
    }
    if set(driver) != required_fields:
        die(f"{arm}: driver fields drift")
    graph = arm == "segmented-graph"
    expected_compilation = {
        "cudagraph_capture_sizes": [8],
        "cudagraph_mode": "PIECEWISE" if graph else "NONE",
        "max_cudagraph_capture_size": 8,
        "mode": "NONE",
    }
    expected_speculative = {
        "draft_sample_method": "greedy",
        "method": "dflash",
        "model": "/mnt/fast-ai/llm-models/laguna-s-2.1/dflash-int4",
        "num_speculative_tokens": 7,
        "rejection_sample_method": "standard",
        "revision": DRAFT_REVISION,
    }
    expected_engine = {
        "all2all_backend": "allgather_reducescatter",
        "async_scheduling": False,
        "block_size": 64,
        "data_parallel_size": 1,
        "distributed_executor_backend": "mp",
        "dtype": "bfloat16",
        "enable_expert_parallel": True,
        "enable_prefix_caching": False,
        "enforce_eager": False,
        "generation_config": "vllm",
        "gpu_memory_utilization": 0.90,
        "kv_cache_dtype": "bfloat16",
        "max_model_len": 8192,
        "max_num_batched_tokens": 8192,
        "max_num_seqs": 1,
        "model": "/mnt/fast-ai/llm-models/laguna-s-2.1/int4",
        "pipeline_parallel_size": 1,
        "revision": TARGET_REVISION,
        "tensor_parallel_size": 4,
        "tokenizer": "/mnt/fast-ai/llm-models/laguna-s-2.1/int4",
        "tokenizer_revision": TARGET_REVISION,
        "trust_remote_code": True,
    }
    if (
        driver["schema"] != DRIVER_SCHEMA
        or driver["arm"] != arm
        or driver["single_generate_call"] is not True
        or driver["offline_only"] is not True
        or driver["nonbenchmark"] is not True
        or driver["ignore_eos"] is not True
        or driver["num_cached_tokens"] != 0
        or driver["max_tokens"] != MAX_TOKENS
        or driver["seed"] != SEED
        or driver["prompt_sha256"] != PROMPT_SHA256
        or driver["target_revision"] != TARGET_REVISION
        or driver["draft_revision"] != DRAFT_REVISION
        or driver["model"] != "/mnt/fast-ai/llm-models/laguna-s-2.1/int4"
        or driver["draft_model"] != expected_speculative["model"]
        or driver["model_manifest_sha256"]
        != "45aa105ef4eceaf05cad33012e0752369f77cbbd76f2213ccfe0ce130fa6c0ac"
        or driver["generation_config"] != "vllm"
        or driver["absent_environment"] != ABSENT_ENVIRONMENT
        or driver["compilation_config"] != expected_compilation
        or driver["speculative_config"] != expected_speculative
        or driver["engine_config"] != expected_engine
        or driver["evidence_dir"] != str(arm_root / "evidence")
        or driver["finish_reason"] != "length"
    ):
        die(f"{arm}: invalid driver cold/config/model provenance")
    runtime = driver["runtime"]
    if (
        not isinstance(runtime, dict)
        or set(runtime) != {"vllm_commit", "vllm_module", "vllm_root"}
        or runtime["vllm_commit"] != VLLM_COMMIT
        or runtime["vllm_root"] != "/home/steve/src/laguna-vllm-runtime-graph-20260724"
        or not isinstance(runtime["vllm_module"], str)
        or not runtime["vllm_module"].startswith(runtime["vllm_root"] + "/")
    ):
        die(f"{arm}: runtime identity drift")
    environment = driver["environment"]
    if not isinstance(environment, dict):
        die(f"{arm}: missing frozen environment identity")
    graph_value = "1" if graph else "0"
    required_environment = {
        "CCL_ATL_TRANSPORT": "ofi",
        "CCL_KVS_IFACE": "eno1",
        "CCL_TOPO_P2P_ACCESS": "1",
        "FI_TCP_IFACE": "eno1",
        "HF_HUB_OFFLINE": "1",
        "LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS": "7",
        "ONEAPI_DEVICE_SELECTOR": "level_zero:0,1,2,3",
        "TRANSFORMERS_OFFLINE": "1",
        "TORCH_XCCL_ASYNC_ERROR_HANDLING": "1",
        "VLLM_DISABLE_SHARED_EXPERTS_STREAM": "0",
        "VLLM_KV_CACHE_LAYOUT": "NHD",
        "VLLM_NO_USAGE_STATS": "1",
        "VLLM_SHARED_EXPERTS_STREAM_TOKEN_THRESHOLD": "256",
        "VLLM_TRACE_FUNCTION": "0",
        "VLLM_USE_AOT_COMPILE": "0",
        "VLLM_USE_BREAKABLE_CUDAGRAPH": graph_value,
        "VLLM_XPU_EXPERT_MAP_ROUND_ROBIN": "0",
        "VLLM_XPU_ENABLE_XPU_GRAPH": graph_value,
        "VLLM_XPU_EXACT_SPEC_ATTN": "1",
        "VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE": "1",
        "VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH": "0",
        "VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM": "0",
        "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK": "0",
        "VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH": graph_value,
        "VLLM_XPU_LAGUNA_M8_EVIDENCE": "1",
        "VLLM_XPU_LAGUNA_M8_EVIDENCE_ARM": arm,
        "VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION": "0",
        "VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2": "1",
        "VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE": "0",
        "VLLM_XPU_LAGUNA_M8_GATHER_SHARDED": "0",
        "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE": "1",
        "VLLM_XPU_LAGUNA_M8_REMOTE_ZERO": "0",
        "VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE": "1",
        "VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM": "0",
        "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE": "1",
        "VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM": "0",
        "VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM": "0",
        "VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM": "0",
        "VLLM_XPU_LAGUNA_M8_W1_N_TILE": "64",
        "VLLM_XPU_LAGUNA_PARITY_PROBE": "0",
        "VLLM_XPU_V4_M1_BIASED_TOPK": "0",
        "VLLM_XPU_V4_M1_ROUTER_NORM": "0",
        "XPU_GRAPH": graph_value,
        "ZE_AFFINITY_MASK": "0,1,2,3",
    }
    if environment != required_environment:
        die(f"{arm}: frozen environment identity drift")
    token_ids = _token_ids(driver["token_ids"], f"{arm}:final token IDs")
    usage = driver["usage"]
    if (
        len(token_ids) != MAX_TOKENS
        or driver["token_ids_sha256"] != digest_json(list(token_ids))
        or not isinstance(driver["text_sha256"], str)
        or len(driver["text_sha256"]) != 64
        or any(ch not in "0123456789abcdef" for ch in driver["text_sha256"])
        or not isinstance(usage, dict)
        or set(usage)
        != {
            "cached_tokens",
            "completion_tokens",
            "prompt_tokens",
            "total_tokens",
        }
        or usage["cached_tokens"] != 0
        or not isinstance(usage["prompt_tokens"], int)
        or usage["prompt_tokens"] <= 0
        or usage["completion_tokens"] != len(token_ids)
        or usage["total_tokens"] != usage["prompt_tokens"] + usage["completion_tokens"]
    ):
        die(f"{arm}: invalid offline usage/output provenance")
    return token_ids


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run_root = Path(
        "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs"
    ).resolve(strict=True)
    run_dir = args.run_dir.resolve(strict=True)
    if (
        not run_dir.is_relative_to(run_root)
        or args.run_dir.is_symlink()
        or args.out.resolve(strict=False) != run_dir / "analysis.json"
    ):
        die("run/output path is not the frozen private-NVMe gate layout")
    if args.out.exists():
        die(f"refusing to overwrite {args.out}")
    normalized: dict[str, dict[str, Any]] = {}
    drivers: dict[str, dict[str, Any]] = {}
    token_lists: list[tuple[int, ...]] = []
    for arm in ARMS:
        arm_root = args.run_dir / arm
        drivers[arm] = load_json(arm_root / "driver.json")
        token_lists.append(_validate_driver(arm, arm_root, drivers[arm]))
        normalized[arm] = normalize_evidence(
            arm,
            arm_root / "evidence" / "evidence.json",
            arm_root / "evidence",
        )
    compare(normalized["incumbent-eager"], normalized["segmented-eager"], "A/B")
    compare(normalized["segmented-eager"], normalized["segmented-graph"], "B/C")
    for rank in map(str, RANKS):
        for ordinal, (a, b) in enumerate(
            zip(
                normalized["segmented-eager"]["rank_events"][rank],
                normalized["segmented-graph"]["rank_events"][rank],
                strict=True,
            )
        ):
            if a["collectives"] != b["collectives"]:
                die(f"B/C: rank {rank} event {ordinal} collective bytes differ")
    if len(set(token_lists)) != 1:
        die("A/B/C: final driver token-id lists differ")
    result = {
        "status": "PASS",
        "schema": SCHEMA,
        "nonbenchmark": True,
        "timing_claim": False,
        "pti_trace_claim": False,
        "arms": list(ARMS),
        "checks": {
            "four_ranks_and_four_eligible_events": True,
            "A_B_target_hidden_attention_sampled_raw_bytes": True,
            "B_C_target_hidden_attention_sampled_raw_bytes": True,
            "B_C_97_collective_raw_outputs_per_event_rank": True,
            "single_fresh_offline_generate_per_arm": True,
            "cached_tokens_exactly_zero": True,
            "one_capture_then_all_later_replays": True,
            "final_driver_token_ids_equal": True,
        },
        "evidence_digest": digest_json(normalized),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"laguna M8 actual offline analysis: FAIL: {exc}")
        raise SystemExit(1)
