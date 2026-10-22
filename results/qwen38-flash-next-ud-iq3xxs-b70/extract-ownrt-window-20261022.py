#!/usr/bin/env python3
"""Rebuild the 2026-10-22 one-card window observations from retained receipts; CPU only.

Covers the packet178 portable source rebuild (two fresh loads), the packet179
checkpoint engine's full-suite load, and the packet179 experimental checkpoint
restart-and-continue gate. Every number is read from a tracked receipt; token
equality, the oracle prefix, the merged checkpoint stream and the cold-prefix
time are recomputed independently instead of trusting the receipts' verdicts.
"""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent.relative_to(ROOT).as_posix()
DEST = Path(__file__).with_name("ownrt-measurements-20261022.json")
STAGE2 = "experiments/own-xpu-runtime/stage2"
P178 = f"{STAGE2}/packet178-onecard-portable/one-card"
P179 = f"{STAGE2}/packet179-session-swap/one-card"
SEALED = f"{STAGE2}/packet165-warm-prefill/one-card"
SEALED_LEDGER = f"{HERE}/ownrt-measurements-20261019.json"
REPRO = "repro/qwen38-flash-next-iq3xxs-ownrt-tp1-b70/manifests"
NOTE = "notes/2026-10-21-own-runtime-window-pin-guard-refusal.md"
DESIGN = "experiments/own-xpu-runtime/SESSION-SWAP-DESIGN.md"
ROWS = {
    "packet178-one-card-full512-A-a": f"{P178}/evidence/device-p178-full512-A-a",
    "packet178-one-card-full512-A-b": f"{P178}/evidence/device-p178-full512-A-b",
    "packet179-one-card-full512-A-a": f"{P179}/evidence/device-p179-full512-A-a",
    "packet179-one-card-checkpoint-A-b": f"{P179}/evidence/device-p179-checkpoint-A-b",
}
CHECKPOINT = ROWS["packet179-one-card-checkpoint-A-b"]
LEGS = ("save", "restore1", "restore2")


def load(path):
    return json.loads((ROOT / path).read_text())


def digest(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def utc(ns):
    return datetime.fromtimestamp(ns / 1e9, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def response_signature(summary):
    """Every emitted token of the twelve suite requests plus the 512-input reading request."""
    suite = [(r["prompt_id"], r["prompt_token_sha256"], r["tokens"]) for r in summary["requests"]]
    reading = (summary["prefill_request"]["prompt_token_sha256"], summary["prefill_request"]["tokens"])
    return suite, reading


def window():
    """Lane-A window provenance: coordinator record cross-checked against the row receipts."""
    note = (ROOT / NOTE).read_text()
    head = re.search(r"^## Window result \((\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})–(\d{2}:\d{2}) UTC, runner unit "
                     r"(lanequeue-A\d+), lane A whole-host\)$", note, re.M)
    faults = re.search(r"^Kernel fault count (\d+) → (\d+) across every row\.$", note, re.M)
    assert head and faults
    day, start, end, unit = head.groups()
    bounds = [datetime.fromisoformat(f"{day}T{t}:00+00:00") for t in (start, end)]
    rows, boots, reviews = [], set(), {}
    for name, path in ROWS.items():
        w = load(f"{path}/window.json")
        assert w["passed"] is True and w["device_executed"] is True and w["stop_reasons"] == []
        assert w["child_still_running"] is False and w["returncode"] == 0 and w["sigterm_sent"] is False
        assert w["reservation"]["lane"] == "A" and w["reservation"]["scope"] == "whole-host"
        assert load(f"{path}/lane-coordination.json")["passed"] is True
        began, ended = (datetime.fromtimestamp(w[k] / 1e9, timezone.utc) for k in ("started_utc_ns", "finished_utc_ns"))
        assert bounds[0] <= began < ended <= bounds[1]
        kernel = (ROOT / path / "kernel-window.jsonl").read_text()
        new_kernel_lines = sum(1 for line in kernel.splitlines() if line.strip())
        assert new_kernel_lines == 0
        boots.add(w["reservation"]["boot_id"])
        rows.append({
            "row": name, "screen_unit": w["unit"]["unit"],
            "started_utc": utc(w["started_utc_ns"]), "finished_utc": utc(w["finished_utc_ns"]),
            "child_elapsed_seconds": w["elapsed_seconds"],
            "new_kernel_journal_lines": new_kernel_lines,
            "window_receipt": f"{path}/window.json", "window_receipt_sha256": digest(f"{path}/window.json"),
        })
    for packet in (P178, P179):
        for review in sorted((ROOT / packet / "evidence").glob("lanequeue-review-*.json")):
            relative = review.relative_to(ROOT).as_posix()
            data = json.loads(review.read_text())
            assert data["schema"] == "own-runtime.screen.fault-review.v3"
            boots.add(data["boot_id"])
            reviews[relative] = {"sha256": digest(relative), "fault_count": data["fault_count"], "through": data["through"]}
    assert len(boots) == 1 and len(reviews) == 4
    assert {r["fault_count"] for r in reviews.values()} == {int(faults.group(1))}
    assert all(bounds[0] <= datetime.fromisoformat(r["through"].replace("Z", "+00:00")) <= bounds[1] for r in reviews.values())
    return {
        "lane": "A", "scope": "whole-host", "boot_id": boots.pop(),
        "runner_unit": unit, "utc": f"{day} {start}–{end}",
        "kernel_fault_count": {"before": int(faults.group(1)), "after": int(faults.group(2))},
        "source_note": NOTE,
        "cross_checks": "every row receipt lies inside the noted window, passed with no stop reason, and recorded zero new kernel journal lines; the four admission fault reviews agree with the noted starting count",
        "admission_fault_reviews": reviews,
        "rows": rows,
    }


def full512_row(path, identity, prior):
    summary_path = f"{path}/bracket-summary.json"
    d = load(summary_path)
    assert d["identity"] == identity and load(f"{path}/identity.json")["measurement_identity"] == identity
    assert d["passed"] is True and d["device_executed"] is True and d["realistic_final_gate"]["passed"] is True
    assert d["kind"] == "full512" and d["strict512"] is True and d["cache_zero"] is True and d["lane"] == "A"
    assert d["submission_eligible"] is False
    assert d["quality"]["no_quality_loss_decision"] is False
    assert d["quality"]["all_available_oracle_tokens_exact"] is True
    assert d["quality"]["full_output_oracle_exact"] is False
    prefill = d["prefill"]
    assert prefill["input_tokens"] == 512 and prefill["cached_tokens"] == 0 and prefill["oracle_covered"] is False
    assert abs(prefill["tok_s"] - 512000 / prefill["elapsed_ms"]) < 1e-10
    assert len(d["requests"]) == 12
    classes = {}
    for request in d["requests"]:
        assert request["cached_tokens"] == 0 and request["requested_max_new"] == 512
        times = request["token_timestamps"]
        assert len(times) >= 100 and all(a < b for a, b in zip(times, times[1:]))
        rate = 99 / (times[99] - times[0])
        assert abs(rate - request["tok_s_1_100_intervals_after_ttft"]) < 1e-8
        classes.setdefault(request["prompt_class"], []).append(rate)
        oracle = load(f"{path.rsplit('/evidence/', 1)[0]}/lineage/oracle128/{request['prompt_id']}.json")
        assert request["tokens"][:128] == oracle["tokens"][:128]
    assert len(classes) == 6
    balanced = d["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"]
    assert abs(median(median(v) for v in classes.values()) - balanced) < 1e-8
    if prior is not None:
        assert response_signature(d) == response_signature(prior)
        assert d["fresh_load_repeat"] == {"passed": True, "request_count": 13,
                                          "scope": "all emitted tokens, including EOS/cap and prefill response"}
        assert d["quality"]["fresh_process_determinism_checked"] is True
    row = {
        "evidence": summary_path, "sha256": digest(summary_path),
        "binary_sha256": d["identity"]["binary_sha256"],
        "decode_class_balanced_tok_s": balanced,
        "suite_requests": len(d["requests"]), "response_cap": 512,
        "prefill_tok_s": prefill["tok_s"], "prefill_ttft_ms": prefill["elapsed_ms"],
        "prefill_prompt_loop_tok_s": prefill["native_prompt_loop_tok_s"],
        "request_start_boundary": prefill["request_start_boundary"],
        "full_natural_completion_statistics": d["full_natural_completion_statistics"],
        "quality": d["quality"],
        "fresh_load_repeat": d.get("fresh_load_repeat"),
    }
    return d, row


def sealed_reference():
    """The packet165c rows of the October 19 ledger, verified against the hashes that ledger publishes."""
    ledger = load(SEALED_LEDGER)
    profile = next(p for p in ledger["profiles"] if p["topology"] == "one-card")
    summaries = []
    for row in profile["rows"]:
        assert digest(row["evidence"]) == row["sha256"]
        summaries.append(load(row["evidence"]))
    assert response_signature(summaries[0]) == response_signature(summaries[1])
    return ledger, profile, summaries


def comparison(summary, sealed):
    ledger, profile, summaries = sealed
    assert response_signature(summary) == response_signature(summaries[0])
    return {
        "reference_ledger": SEALED_LEDGER, "reference_ledger_sha256": digest(SEALED_LEDGER),
        "reference_rows": [row["evidence"] for row in profile["rows"]],
        "sealed_binary_sha256": profile["identity"]["binary_sha256"],
        "responses_compared": len(summary["requests"]) + 1,
        "every_emitted_token_identical": True,
        "scope": "all emitted tokens of the twelve suite requests and of the 512-input reading request, including EOS/cap",
    }


def profile_common():
    return {
        "measurement_scope": "Twelve cold suite prompts and one distinct 512-input-token prompt per fresh load; one user; context allocation 4096.",
        "prefill_definition": "512 input tokens / native request TTFT seconds; warm runtime, cold prompt; includes first-token work; not isolated device prefill or HTTP TTFT.",
        "prefill_oracle_covered": False,
        "context_length_sweep": "not measured on this identity",
        "concurrency_sweep": "not measured; controller runs one request at a time",
        "submission_eligible": False,
    }


def rebuild_profile(sealed):
    identity_path = f"{P178}/identity.json"
    identity = load(identity_path)
    build_path = f"{P178}/evidence/build.json"
    build = load(build_path)
    sealed_identity = load(f"{SEALED}/identity.json")
    assert build["schema"] == "neural.download.ownrt.source-build-result.v1" and build["passed"] is True
    assert build["cards"] == 1 and build["reused_object_files"] is False
    assert build["binary_sha256"] == identity["binary_sha256"]
    assert build["archive_sha256"] == digest(f"{REPRO}/native-sources.tar.gz")
    assert build["manifest_sha256"] == digest(f"{REPRO}/native-build.json")
    assert build["build_validation_sha256"] == digest(f"{REPRO}/build-validation.json")
    assert build["historical_binary_sha256"] == sealed_identity["binary_sha256"] == identity["parent_binary_sha256"]
    assert build["historical_binary_hash_matches"] is (build["binary_sha256"] == sealed_identity["binary_sha256"]) is False
    assert identity["native_arithmetic_unchanged_from_packet163"] is True
    (compiler,) = build["compiler_versions"].values()
    rows, summaries = [], []
    for name in ("packet178-one-card-full512-A-a", "packet178-one-card-full512-A-b"):
        summary, row = full512_row(ROWS[name], identity, summaries[-1] if summaries else None)
        summaries.append(summary)
        rows.append(row)
    return {
        "topology": "one-card", "profile": "packet178 portable source rebuild",
        "identity": identity, "identity_evidence": identity_path, "identity_sha256": digest(identity_path),
        "build": {
            "evidence": build_path, "sha256": digest(build_path),
            "binary_sha256": build["binary_sha256"], "binary_bytes": build["binary_bytes"],
            "source_archive": f"{REPRO}/native-sources.tar.gz", "source_archive_sha256": build["archive_sha256"],
            "build_manifest": f"{REPRO}/native-build.json", "build_manifest_sha256": build["manifest_sha256"],
            "cpu_build_validation": f"{REPRO}/build-validation.json", "cpu_build_validation_sha256": build["build_validation_sha256"],
            "relocated_source_root": build["relocated_source_root"],
            "reused_object_files": False,
            "compiler": compiler.splitlines()[0],
            "sealed_binary_sha256": build["historical_binary_sha256"],
            "binary_bytes_identical_to_sealed": False,
            "status_at_build": build["status"],
        },
        "device_qualification": {
            "fresh_loads": len(rows), "oracle_128_exact": True,
            "fresh_load_repeat": rows[1]["fresh_load_repeat"],
            "sealed_line_comparison": comparison(summaries[0], sealed),
            "package_binary": "unchanged: the one-card package still pins and measures the sealed packet165 binary",
            "two_card_rebuild": "not device-qualified; this window ran one-card rows only",
        },
        **profile_common(), "rows": rows,
    }


def checkpoint_engine_profile(sealed, rebuild_summary):
    identity_path = f"{P179}/identity.json"
    identity = load(identity_path)
    assert identity["parent_binary_sha256"] == load(f"{SEALED}/identity.json")["binary_sha256"]
    summary, row = full512_row(ROWS["packet179-one-card-full512-A-a"], identity, None)
    assert response_signature(summary) == response_signature(rebuild_summary)
    return summary, {
        "topology": "one-card", "profile": "packet179 checkpoint engine (packet165 relink), full-suite load",
        "identity": identity, "identity_evidence": identity_path, "identity_sha256": digest(identity_path),
        "sealed_line_comparison": comparison(summary, sealed),
        "single_fresh_load": "the packet's second row is the checkpoint gate below, not a second full-suite load",
        **profile_common(), "rows": [row],
    }


def checkpoint(reference_summary, identity):
    summary_path = f"{CHECKPOINT}/bracket-summary.json"
    receipt_path = f"{CHECKPOINT}/run/checkpoint-receipt.json"
    manifest_path = f"{CHECKPOINT}/run/checkpoints/gate/manifest.json"
    d, receipt, manifest = load(summary_path), load(receipt_path), load(manifest_path)
    assert load(f"{CHECKPOINT}/identity.json")["measurement_identity"] == identity
    assert d["source_receipt_sha256"] == digest(receipt_path)
    assert d["manifest_sha256"] == receipt["manifest_sha256"] == digest(manifest_path)
    assert d["manifest"] == receipt["manifest"] == manifest
    assert d["passed"] is True and d["device_executed"] is True and d["kind"] == "checkpoint" and d["lane"] == "A"
    assert d["submission_eligible"] is False and d["experimental_checkpoint"] is True and d["strict512"] is False
    assert manifest["format"] == "ownrt.session-checkpoint.v1" and manifest["label"] == "experimental"
    assert manifest["engine"]["binary_sha256"] == identity["binary_sha256"]
    assert manifest["engine"]["packet"] == "packet179-session-swap"
    assert manifest["sampler"] == {"mode": "greedy-argmax", "state": None}
    blobs = manifest["blobs"]
    assert sum(b["bytes"] for b in blobs) == d["save_bytes"] == manifest["measurements"]["save_bytes"]
    assert d["save_seconds"] == manifest["measurements"]["save_seconds"]
    k, m = d["save_max_new"], d["restore_max_new"]
    legs = {}
    for leg in LEGS:
        base = f"{CHECKPOINT}/run/run/{leg}"
        result, native = load(f"{base}/native/result.json"), load(f"{base}/native/receipt.json")
        argv = load(f"{base}/launch.json")["argv"]
        log_tokens = [int(t) for t in re.findall(r"^token_id (\d+)$", (ROOT / base / "native.log").read_text(), re.M)]
        assert result["passed"] is True and native["passed"] is True and native["device_executed"] is True
        assert result["tokens"] == native["tokens"] == log_tokens and result["cached_tokens"] == 0
        assert result["prompt_tokens"] == d["prompt_tokens"]
        assert native["model_payload_bytes_read"] > 8 * 10**10  # each leg is its own process with its own full model load
        assert ("--checkpoint-save" if leg == "save" else "--checkpoint-restore") in argv
        legs[leg] = (base, result)
    save, restore1, restore2 = (legs[leg][1] for leg in LEGS)
    eos = re.search(r"^EOS=\(([0-9, ]+)\)$", (ROOT / P179 / "measurement.py").read_text(), re.M)
    eos = {int(t) for t in eos.group(1).split(",")}
    assert len(save["tokens"]) == k and save["checkpoint_restore_ms"] is None
    assert d["save_eos_free"] is True and not eos & set(save["tokens"])
    assert restore1["tokens"] == restore2["tokens"] and len(restore1["tokens"]) == m
    assert all(legs[leg][1]["prefill_ms"] == 0 and legs[leg][1]["checkpoint_restore_ms"] > 0 for leg in LEGS[1:])
    # The K-th generated token is the saved pending token; the cache holds the prompt plus K-1 fed tokens.
    state = manifest["token_state"]
    assert state["prompt_length"] == d["prompt_tokens"] and state["length"] == state["position"] == d["prompt_tokens"] + k - 1
    assert state["next_token"] == save["tokens"][-1]
    reference = next(r for r in reference_summary["requests"] if r["prompt_id"] == d["prompt_id"])
    reference_result = f"{ROWS['packet179-one-card-full512-A-a']}/run/native/{d['prompt_id']}/result.json"
    assert digest(reference_result) == d["reference_result_sha256"]
    assert load(reference_result)["tokens"] == reference["tokens"]
    merged = save["tokens"] + restore1["tokens"]
    assert merged == reference["tokens"][:k + m] and d["merged_tokens"] == d["reference_tokens_compared"] == k + m
    oracle = load(f"{P179}/lineage/oracle128/{d['prompt_id']}.json")
    assert merged[:128] == oracle["tokens"][:128] and d["oracle_check"]["passed"] is True
    times = reference["token_timestamps"]
    cold_prefix_ms = (times[k - 1] - times[0]) * 1000 + reference["ttft_ms"]
    assert abs(cold_prefix_ms - d["cold_prefix_ms"]) < 1e-6
    restores = []
    for leg in LEGS[1:]:
        base, result = legs[leg]
        restores.append({
            "leg": leg, "result": f"{base}/native/result.json", "sha256": digest(f"{base}/native/result.json"),
            "restore_ms": result["checkpoint_restore_ms"], "prompt_recompute_ms": result["prefill_ms"],
            "continuation_tokens": len(result["tokens"]),
            "continuation_wall_ms": 1000 * (result["request_end_monotonic"] - result["request_start_monotonic"]),
        })
    assert restores[0]["restore_ms"] == d["restore_ms"]
    assert abs(restores[0]["continuation_wall_ms"] - d["restore_continuation_wall_ms"]) < 1e-6
    return {
        "evidence": summary_path, "sha256": digest(summary_path),
        "receipt": receipt_path, "receipt_sha256": digest(receipt_path),
        "manifest": manifest_path, "manifest_sha256": d["manifest_sha256"],
        "manifest_format": manifest["format"], "label": manifest["label"],
        "operation": "same-generation save/restart/resume",
        "operation_source": f"{DESIGN} v1.2",
        "not_implemented": ["appending a new turn to a restored prefix", "restoring and then saving again"],
        "engine_binary_sha256": manifest["engine"]["binary_sha256"],
        "engine_native_delta": identity["native_delta"],
        "prompt_id": d["prompt_id"], "prompt_tokens": d["prompt_tokens"],
        "save": {
            "result": f"{legs['save'][0]}/native/result.json", "sha256": digest(f"{legs['save'][0]}/native/result.json"),
            "generated_tokens_before_save": k, "eos_free": d["save_eos_free"],
            "seconds": d["save_seconds"], "bytes": d["save_bytes"],
            "blob_count": len(blobs), "skipped_buffer_count": len(manifest["skipped_buffers"]),
            "blob_bytes_sum_equals_save_bytes": True,
            "blobs_in_git": False,
            "blob_storage": "blob bytes are not tracked; the tracked manifest records each blob's size and SHA-256",
        },
        "fresh_process_restores": restores,
        "merged_tokens": k + m, "reference_tokens_compared": k + m,
        "merged_equals_uninterrupted_reference": True,
        "repeat_restores_identical": True,
        "oracle_128_exact_on_merged_stream": True,
        "beyond_oracle_status": d["oracle_check"]["beyond_oracle_status"],
        "reference": {"evidence": f"{ROWS['packet179-one-card-full512-A-a']}/bracket-summary.json",
                      "result": reference_result, "result_sha256": d["reference_result_sha256"]},
        "cold_prefix_ms": cold_prefix_ms, "cold_prefix_definition": d["cold_prefix_definition"],
        "gate_scope": receipt["scope"],
        "submission_eligible": False, "experimental": True,
        "independent_checks": "merged stream, repeat restores, oracle prefix and cold-prefix time recomputed from the per-leg native results, native logs and the reference row",
    }


def extract():
    sealed = sealed_reference()
    rebuild = rebuild_profile(sealed)
    rebuild_summary = load(rebuild["rows"][0]["evidence"])
    reference_summary, engine = checkpoint_engine_profile(sealed, rebuild_summary)
    return {
        "schema": "neural.download.ownrt-observations.v1",
        "window": window(),
        "profiles": [rebuild, engine],
        "checkpoint": checkpoint(reference_summary, engine["identity"]),
        "scope": "Measured lab observations from one lane-A window, not a promotion attestation. Exact oracle covers the first 128 output tokens only; longer outputs and the reading response are compared token-for-token across fresh loads and against the sealed packet165c rows. The checkpoint gate is an experimental correctness gate, not a performance claim.",
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="write the derived JSON; otherwise verify it")
    args = ap.parse_args()
    expected = json.dumps(extract(), indent=2, ensure_ascii=False) + "\n"
    if args.write:
        DEST.write_text(expected)
    elif DEST.read_text() != expected:
        raise SystemExit("Observation table differs from retained evidence")
    print("PASS: 2026-10-22 window, three full-suite loads and one checkpoint gate; exact values, token identity and quality limits retained")


if __name__ == "__main__":
    main()
