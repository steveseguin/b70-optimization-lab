#!/usr/bin/env python3
"""Verify retained FP8 synthetic prefill evidence and rebuild observations; CPU only."""
import argparse
import ast
import hashlib
import io
import json
import math
from pathlib import Path
import re
from statistics import median
import tarfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/2026-10-20-fp8-one-launch-prefill"
PACKAGE = ROOT / "packages/qwen38-27b-fp8-tp2-b70/package.json"
EVIDENCE = "data/2026-10-20-fp8-one-launch-prefill/summary.json"
SCOPE = (
    "October 20 synthetic screen on steve-b70s, two selected B70s, one persistent "
    "server, recommended FP8 overlay 0.2.0, MTP5, one user, 33024-token capacity. "
    "Six requests: two repeats each of prose/code/docs, exact 512 input tokens, "
    "128 forced output tokens (ignore_eos), zero cached tokens. Reading is input "
    "tokens / one-request server prefill histogram duration, not isolated kernel "
    "throughput or HTTP TTFT. Writing uses 99 intervals between tokens 1 and 100 "
    "from SSE arrival timestamps. TTFT includes the passive request-admission "
    "guard. Warmups are excluded. Full output IDs match within each repeated "
    "class; no no-MTP oracle comparison was made. These observations are not "
    "a new headline or quality promotion and do not pool with turin measurements."
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def equal_number(a, b):
    assert type(a) in (float, int) and type(b) in (float, int)
    assert math.isfinite(a) and math.isfinite(b) and math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12), (a, b)


def load_evidence():
    manifest = json.loads((BASE / "manifest.json").read_text())
    archive = (BASE / manifest["archive"]).read_bytes()
    assert digest(archive) == manifest["archive_sha256"], "archive digest mismatch"
    files = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tf:
        for member in tf.getmembers():
            assert member.isfile() and member.name not in files
            assert not Path(member.name).is_absolute() and ".." not in Path(member.name).parts
            files[member.name] = tf.extractfile(member).read()
    assert set(files) == {f["path"] for f in manifest["files"]}
    for item in manifest["files"]:
        data = files[item["path"]]
        assert len(data) == item["bytes"] and digest(data) == item["sha256"], item["path"]
    return files, manifest


def metric_values(data):
    result = {}
    for line in data.decode().splitlines():
        match = re.match(r'([^\s{]+)(?:\{[^}]*\})?\s+([-+0-9.eE]+)(?:\s|$)', line)
        if match:
            name, value = match.groups()
            for suffix in ("request_prefill_time_seconds_sum", "request_prefill_time_seconds_count", "prompt_tokens_total"):
                if name.endswith(suffix):
                    result[suffix] = result.get(suffix, 0.0) + float(value)
    return result


def extract(files, manifest):
    def obj(name):
        return json.loads(files[name])
    identity = obj("run/identity.json")
    assert identity["host"] == "steve-b70s"
    assert identity["device_pci_mapping"] == {"renderD130": "0000:23:00.0", "renderD131": "0000:27:00.0"}
    assert identity["no_quality_loss_gate"] is False and identity["strict_headline_eligible"] is False
    assert digest(files["preregistration.json"]) == identity["preregistration_sha256"]
    prereg = obj("preregistration.json")
    assert prereg["source_files"] == identity["source_files"]
    for item in identity["source_files"]:
        assert digest(files["source/" + item["path"]]) == item["sha256"], item["path"]
    # Read the exact pinned launcher's fault expression without executing source.
    tree = ast.parse(files["source/packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py"])
    fault_definition = next(node for node in tree.body if isinstance(node, ast.Assign)
                            and any(isinstance(t, ast.Name) and t.id == "FAULT" for t in node.targets))
    fault = re.compile(ast.literal_eval(fault_definition.value.args[0]), re.I)
    for path, data in files.items():
        if path.startswith("run/") and path.endswith("kernel.log"):
            assert not fault.search(data.decode()), f"GPU fault in {path}"
    launch = obj("run/server/launch.json")["argv"]
    checked = obj("run/launch-identity-check.json")
    assert checked["matched"] is True and checked["argv"] == launch
    expected = identity["launch_argv_template"].copy()
    expected[expected.index("--name") + 1] = launch[launch.index("--name") + 1]
    assert expected == launch
    assert "B70_FA_VERIFY_ROWS_ONE_LAUNCH=1" in launch
    verification = obj("run/model-verification.json")
    assert verification["status"] == "verified"
    assert verification["files"] and all(item["ok"] for item in verification["files"])
    lifecycle = obj("run/server-lifecycle.json")
    assert lifecycle["error"] is None and lifecycle["drained"] is True
    assert lifecycle["no_retry"] is True and lifecycle["no_sigkill"] is True
    assert obj("run/server/graceful-stop.json")["stopped"] is True
    assert obj("run/server/graceful-stop.json")["escalation"] is False
    stop = obj("run/server/stop-request.json")
    assert stop["signal"] == "SIGTERM" and stop["escalation"] == "none"
    assert obj("run/server/state.json")["profile"] == "recommended"
    assert not any(Path(p).name in ("FAULT.json", "HALTED.json") for p in files)
    summary = obj("run/screen/summary.json")
    assert summary["passed"] is True and summary["args"]["baseline"] is None
    for key, value in {"lengths": "512", "max_tokens": 128, "repeats": 2, "max_model_len": 33024}.items():
        assert summary["args"][key] == value
    assert len(summary["rows"]) == 6 and len(summary["warmups"]) == 1
    assert {(r["key"], r["repeat"]) for r in summary["rows"]} == {
        (name + "-512", repeat) for name in ("prose", "code", "docs") for repeat in (0, 1)}
    rows, prior = [], {}
    for record in summary["warmups"] + summary["rows"]:
        key, phase, repeat = record["key"], record["phase"], record["repeat"]
        stem = f"run/screen/{phase}-{key}-{repeat}"
        payload = obj(stem + "-request.json")
        prompt = payload["prompt"]
        assert len(prompt) == 512 and all(type(t) is int for t in prompt)
        assert prompt == summary["prompts"][key]
        assert payload["ignore_eos"] is True and payload["max_tokens"] == 128
        assert payload["temperature"] == 0 and payload["seed"] == 42 and payload["n"] == 1
        ids, offsets, usage, done = [], [], None, False
        for line in files[stem + "-sse.jsonl"].splitlines():
            event = json.loads(line)
            if event["data"] == "[DONE]":
                done = True
                continue
            data = json.loads(event["data"])
            assert not data.get("error")
            if data.get("usage") is not None:
                usage = data["usage"]
            for choice in data.get("choices", []):
                assert choice.get("index", 0) == 0
                tokens = choice.get("token_ids", [])
                assert all(type(t) is int for t in tokens)
                ids.extend(tokens)
                offsets.extend([event["elapsed_s"]] * len(tokens))
        assert done and len(ids) == 128 and len(offsets) == 128
        assert usage["prompt_tokens"] == 512 and usage["completion_tokens"] == 128
        assert usage["prompt_tokens_details"]["cached_tokens"] == 0
        assert ids == record["token_ids"] and offsets == record["token_offsets_s"] and usage == record["usage"]
        assert all(a <= b for a, b in zip(offsets, offsets[1:])) and offsets[99] > offsets[0] > 0
        decode = 99 / (offsets[99] - offsets[0])
        equal_number(decode, record["decode_token_1_to_100_tps"])
        equal_number(offsets[0], record["ttft_s"])
        equal_number(512 / offsets[0], record["http_prompt_tokens_per_ttft_s"])
        before = metric_values(files[stem + "-metrics-before.txt"])
        after = metric_values(files[stem + "-metrics-after.txt"])
        delta = {k: after[k] - before[k] for k in after}
        assert delta["request_prefill_time_seconds_count"] == 1
        assert delta["prompt_tokens_total"] == 512
        seconds = delta["request_prefill_time_seconds_sum"]
        assert seconds > 0
        prefill = 512 / seconds
        equal_number(seconds, record["server_prefill_s"])
        equal_number(prefill, record["server_prefill_tokens_per_s"])
        if phase == "warmup":
            continue
        assert phase == "measure"
        if key in prior:
            assert prior[key] == (prompt, ids), "repeat input/output token IDs differ"
        prior[key] = (prompt, ids)
        rows.append({
            "label": f"{key.split('-')[0].capitalize()} repeat {repeat + 1}",
            "status": "synthetic ignore_eos screen; no new quality attestation",
            "evidence": EVIDENCE, "raw_evidence_stem": stem,
            "prompt_token_ids_sha256": digest(json.dumps(prompt, separators=(",", ":")).encode()),
            "output_token_ids_sha256": digest(json.dumps(ids, separators=(",", ":")).encode()),
            "decode_tok_s": decode, "prefill_tok_s": prefill,
            "prefill_input_tokens": 512, "server_prefill_ms": seconds * 1000,
            "ttft_ms": offsets[0] * 1000, "http_prompt_tokens_per_ttft_s": 512 / offsets[0],
            "response_cap": 128, "cached_tokens": 0, "samples": 1,
        })
    rates = [r["prefill_tok_s"] for r in rows]
    equal_number(median(rates), summary["by_length"]["512"]["server_prefill_tokens_per_s"])
    return {
        "schema": "neural.download.fp8-synthetic-prefill.v1", "scope": SCOPE,
        "archive_sha256": manifest["archive_sha256"], "preregistration_sha256": identity["preregistration_sha256"],
        "host": identity["host"], "device_pci_mapping": identity["device_pci_mapping"],
        "source_files": identity["source_files"], "launch_argv": launch,
        "model_revision": prereg["model_revision"], "runtime_profile": "recommended",
        "overlay_version": "0.2.0", "headline_eligible": False, "no_quality_loss_gate": False,
        "quality_scope": "Three repeated full numeric outputs match; no no-MTP oracle comparison in this screen.",
        "prefill_aggregate": {"method": "median of all six request-level rates; warmups excluded",
                            "median_tok_s": median(rates), "min_tok_s": min(rates), "max_tok_s": max(rates), "samples": 6},
        "server_lifecycle": lifecycle, "rows": rows,
    }


def measurements(result):
    return {"scope": SCOPE, "evidence": EVIDENCE, "rows": [
        {k: row[k] for k in ("label", "status", "evidence", "decode_tok_s", "prefill_tok_s",
                             "prefill_input_tokens", "ttft_ms", "response_cap", "samples")}
        for row in result["rows"]]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write verified summary and package observation table")
    args = parser.parse_args()
    result = extract(*load_evidence())
    expected = json.dumps(result, indent=2) + "\n"
    package = json.loads(PACKAGE.read_text())
    if args.write:
        (BASE / "summary.json").write_text(expected)
        package["text_measurements"] = measurements(result)
        PACKAGE.write_text(json.dumps(package, indent=2, ensure_ascii=False) + "\n")
    else:
        assert (BASE / "summary.json").read_text() == expected, "derived summary drift"
        assert package["text_measurements"] == measurements(result), "package observation drift"
    print("PASS: 91 hash-bound files, exact source/launch, six 512/128 requests, zero cache, repeated IDs, 99 intervals, histogram rates, TERM drain")


if __name__ == "__main__":
    main()
