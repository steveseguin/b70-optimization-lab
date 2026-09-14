#!/usr/bin/env python3
"""Collect compact coding-worker receipts; verify without the original host.

Run only after all five selected runs have result.json. Live server logs are
copied at their observed byte length; this is a timestamped capture, not a stop
or a postflight. No server, GPU, or model operations are performed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import statistics
import tarfile


RUNS = ("lab-download-manifest-paths-v2", "lab-smoke-first-request-failure",
        "ml-hardware-listing-isolation-v2", "ml-zero-electricity-cost", "ml-predict-cli-numeric-errors")
INVALID = "lab-download-manifest-paths"
MODEL_LIMIT = "ml-hardware-listing-isolation"
EXCLUDED_DIRS = {"baseline", "workspace", "cache", "mini-config", ".git", "__pycache__"}
EXCLUDED_FILES = {"source.tar"}
MAX_MEMBER_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_MEMBERS = 10_000


class IntegrityError(RuntimeError):
    pass


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n").encode()


def now():
    return datetime.now(timezone.utc).isoformat()


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def aggregate(calls):
    def values(key):
        return [call[key] for call in calls if finite_number(call.get(key))]
    def median(key):
        rows = values(key)
        return {"median": statistics.median(rows) if rows else None, "measured_calls": len(rows)}
    prompts = values("prompt_tokens")
    outputs = values("completion_tokens")
    return {"completed_calls": len(calls),
            "prompt_token_range": [min(prompts), max(prompts)] if prompts else None,
            "completion_token_range": [min(outputs), max(outputs)] if outputs else None,
            "server_prefill_tokens_s": median("server_prefill_tokens_s"),
            "server_prefill_s": median("server_prefill_s"),
            "http_ttft_s": median("http_ttft_s"),
            "decode_stream_proxy_tokens_s": median("decode_stream_proxy_tokens_s")}


def public_files(members):
    files = {}
    for run in RUNS:
        result = json.loads(members[run + "/result.json"])
        task_id = result.get("task_id")
        if not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", task_id):
            raise IntegrityError("invalid public task identifier: " + run)
        for folder, extension, member in (("patches", ".patch", run + "/changes.patch"),
                                           ("reviews", ".md", run + "/independent-review.md")):
            if members.get(member):
                name = folder + "/" + task_id + extension
                if name in files:
                    raise IntegrityError("duplicate public task identifier: " + task_id)
                files[name] = member
    return files


def summaries(members):
    """Recompute compact summaries from archived source receipts, never booleans alone."""
    sources = {}
    projections = public_files(members)
    def read_bytes(name):
        if name not in members:
            raise IntegrityError("missing required evidence: " + name)
        sources[name] = sha(members[name])
        return members[name]
    def read(name):
        return json.loads(read_bytes(name))

    capture = read("capture.json")
    all_calls = []
    def summarize_run(run):
        result = read(run + "/result.json")
        task = read(run + "/task.json")
        baseline = read(run + "/baseline-validation.json")
        sandbox = read(run + "/sandbox.json")
        expected_error = task.get("expected_baseline_error")
        baseline_matches = (not task.get("expected_baseline_failure") or
                            (type(baseline.get("returncode")) is int and baseline["returncode"] != 0
                             and (not expected_error or expected_error in baseline.get("output", ""))))
        calls = result.get("requests", [])
        if result.get("model_requests") != len(calls):
            raise IntegrityError("request count differs from recorded attempts: " + run)
        completed = []
        output_token_checks = []
        directories = set()
        for call in calls:
            directory = call.get("directory")
            if not isinstance(directory, str) or not directory.isdigit() or directory in directories:
                raise IntegrityError("invalid or duplicate request directory: " + run)
            directories.add(directory)
            if call.get("status") != "completed":
                continue
            prefix = run + "/requests/" + directory
            attempt = read(prefix + "/attempt.json")
            if attempt != call:
                raise IntegrityError("attempt receipt differs from result: " + prefix)
            response = read(prefix + "/response.json")
            if sha(response["text"].encode()) != response.get("text_sha256"):
                raise IntegrityError("response text hash mismatch: " + prefix)
            if (type(response.get("cached_tokens")) is not int or response["cached_tokens"] != 0
                    or response.get("usage", {}).get("prompt_tokens_details", {}).get("cached_tokens") != 0):
                raise IntegrityError("completed response is not explicitly cache-zero: " + prefix)
            count_path = prefix + "/token-count.json"
            if count_path in members and read(count_path).get("input_tokens") != response.get("prompt_tokens"):
                raise IntegrityError("actual prompt length differs from token-count receipt: " + prefix)
            token_ids = response.get("token_ids")
            if response.get("token_ids_available"):
                if (not isinstance(token_ids, list) or len(token_ids) != response.get("completion_tokens")
                        or any(type(value) is not int or value < 0 for value in token_ids)):
                    raise IntegrityError("full output token coverage is inconsistent: " + prefix)
                stream_ids, stream_text, done = [], [], False
                for frame in read_bytes(prefix + "/response.sse").decode().replace("\r\n", "\n").split("\n\n"):
                    lines = [line[5:].removeprefix(" ") for line in frame.splitlines() if line.startswith("data:")]
                    if not lines:
                        continue
                    data = "\n".join(lines)
                    if data == "[DONE]":
                        done = True
                        break
                    event = json.loads(data)
                    if event.get("error"):
                        raise IntegrityError("error in completed raw stream: " + prefix)
                    for choice in event.get("choices", []):
                        stream_ids.extend(choice.get("token_ids") or [])
                        stream_text.append((choice.get("delta") or {}).get("content") or "")
                if not done or stream_ids != token_ids or "".join(stream_text) != response["text"]:
                    raise IntegrityError("full output differs from raw stream: " + prefix)
                output_token_checks.append({"directory": directory, "token_ids": len(token_ids),
                                            "token_ids_sha256": sha(json.dumps(token_ids, separators=(",", ":")).encode()),
                                            "matched_raw_stream": True})
            keys = {"prompt_tokens": "prompt_tokens", "completion_tokens": "completion_tokens",
                    "http_ttft_s": "http_ttft_s", "server_prefill_s": "server_prefill_s",
                    "server_prefill_tokens_s": "server_prefill_tokens_per_s",
                    "decode_stream_proxy_tokens_s": "decode_stream_proxy_tokens_s", "elapsed_s": "elapsed_s"}
            for key, response_key in keys.items():
                if call.get(key) != response.get(response_key):
                    raise IntegrityError("request metric differs from response: " + prefix + " " + key)
            prefill = response.get("server_prefill_s")
            if finite_number(prefill):
                delta = response.get("raw_delta", {})
                if (prefill <= 0 or delta.get("vllm:request_prefill_time_seconds_count") != 1
                        or delta.get("vllm:request_prefill_time_seconds_sum") != prefill
                        or delta.get("vllm:prompt_tokens_total") != response.get("prompt_tokens")
                        or not math.isclose(response["prompt_tokens"] / prefill,
                                            response["server_prefill_tokens_per_s"], rel_tol=1e-12)):
                    raise IntegrityError("server-prefill measurement definition mismatch: " + prefix)
            completed.append(dict(call))
        patch = result.get("patch")
        if patch:
            changes = read(run + "/changes.json")
            if changes != patch or sha(members.get(run + "/changes.patch", b"")) != patch.get("patch_sha256"):
                raise IntegrityError("patch receipt mismatch: " + run)
        validation_paths = sorted(name for name in members if name.startswith(run + "/validation-") and name.endswith(".json"))
        validations = [read(name) for name in validation_paths]
        # A runner's success must still be supported by its accepted tree receipt.
        supported = bool(result.get("acceptance_passed") and result.get("agent_result", {}).get("exit_status") == "Submitted"
                         and validations and validations[-1].get("accepted") is True
                         and validations[-1].get("returncode") == 0
                         and validations[-1].get("workspace_stable") is True
                         and result.get("acceptance_tree_sha256")
                         and result["acceptance_tree_sha256"] == result.get("final_workspace_tree_sha256")
                         and result["acceptance_tree_sha256"] == validations[-1].get("workspace_after_sha256")
                         and result.get("final_workspace_matches_acceptance") is True
                         and patch and patch.get("changed_files") and patch.get("source_repo_unchanged") is True
                         and patch.get("baseline_unchanged") is True and sandbox.get("stopped") is True
                         and baseline_matches)
        if result.get("acceptance_passed") and not supported:
            raise IntegrityError("claimed acceptance lacks matching tree and validation evidence: " + run)
        reviews = sorted(name for name in members if (name.startswith(run + "/") or name.startswith("independent-review/"))
                         and "review" in name and name.endswith((".json", ".txt", ".md", ".log")))
        review_receipts = []
        for name in reviews:
            if name.startswith("independent-review/") and not (run in name or result.get("task_id", "__missing__") in name):
                continue
            sources[name] = sha(members[name])
            review_receipts.append({"path": name, "sha256": sha(members[name]),
                                    "recorded_review": json.loads(members[name]) if name.endswith(".json") else None})
        return {"run": run, "task_id": result.get("task_id"), "recorded_status": result.get("status"),
                "acceptance_supported_by_receipts": supported, "error": result.get("error"),
                "model_requests": result["model_requests"], "unfinished_or_failed_requests": len(calls) - len(completed),
                "elapsed_seconds": result.get("elapsed_seconds"), "source_commit": result.get("source_commit"),
                "model": result.get("model"), "sandbox_image": result.get("sandbox_image"),
                "patch_sha256": patch.get("patch_sha256") if patch else None,
                "changed_files": [row["path"] for row in patch.get("changed_files", [])] if patch else [],
                "metrics": aggregate(completed), "human_review": result.get("human_review", "unknown"),
                "baseline_returncode": baseline.get("returncode"),
                "expected_baseline_failure": bool(task.get("expected_baseline_failure")),
                "expected_baseline_error": expected_error, "baseline_matches_expected_failure": baseline_matches,
                "cpu_sandbox_recorded_stopped": sandbox.get("stopped") is True,
                "full_output_token_checks": output_token_checks,
                "public_patch": next((name for name, member in projections.items() if member == run + "/changes.patch"), None),
                "public_review": next((name for name, member in projections.items() if member == run + "/independent-review.md"), None),
                "independent_review_receipts": review_receipts}, completed

    runs = []
    for name in RUNS:
        row, calls = summarize_run(name)
        runs.append(row)
        all_calls.extend(calls)
    invalid, _ = summarize_run(INVALID)
    invalid["classification"] = "infrastructure-invalid first attempt; preserved separately, excluded from five-run aggregate"
    model_limit, _ = summarize_run(MODEL_LIMIT)
    model_limit["classification"] = "incomplete model attempt: repeated read commands reached the step limit; not an infrastructure failure; excluded from selected-run aggregate"
    state = read("server/state.json")
    summary = {"schema": "neural.download.local-worker-five-issues.v1", "runs": runs,
               "selected_runs": list(RUNS), "selected_tasks": len(RUNS),
               "accepted_tasks": sum(row["acceptance_supported_by_receipts"] for row in runs),
               "requests_total": sum(row["model_requests"] for row in runs), "metrics": aggregate(all_calls),
               "elapsed_seconds_total": sum(row["elapsed_seconds"] for row in runs if finite_number(row["elapsed_seconds"])),
               "human_review": "pending; independent technical review receipts are reported separately",
               "verification_scope": "archive integrity and consistency of recorded baseline, acceptance, teardown and request evidence; verification does not rerun tests or establish quality beyond those checks",
               "metric_scope": "observed coding-session calls with varying prompt/output lengths; no controlled speed promotion or broad coding benchmark",
               "server_prefill_definition": "prompt tokens divided by the single-request server prefill counter duration; HTTP TTFT is separate",
               "decode_definition": "streamed token-ID intervals divided by chunk-arrival duration; transport proxy, not server decode timing",
               "server_capture": {"started_at": capture["started_at"], "finished_at": capture["finished_at"],
                                  "recorded_state": state, "scope": "copy of live files at capture time; no server stop or new postflight inferred"},
               "invalid_first_attempt_summary": "invalid-attempt-summary.json",
               "model_limit_attempt_summary": "model-limit-attempt-summary.json", "source_checks": sources}
    return summary, invalid, model_limit


def collect_members(raw_root):
    started = now()
    members, copies, excluded = {}, {}, []
    allowed_dirs = set(RUNS) | {INVALID, MODEL_LIMIT, "server", "health", "setup-sandbox", "independent-review", "reviews"}
    for directory, dirs, files in os.walk(raw_root, followlinks=False):
        parent = Path(directory)
        for name in list(dirs):
            path = parent / name
            if path.is_symlink() or name in EXCLUDED_DIRS or (parent == raw_root and name not in allowed_dirs):
                dirs.remove(name)
                excluded.append(path.relative_to(raw_root).as_posix())
        for name in sorted(files):
            path = parent / name
            relative = path.relative_to(raw_root).as_posix()
            info = path.lstat()
            if name in EXCLUDED_FILES or not stat.S_ISREG(info.st_mode):
                excluded.append(relative)
                continue
            if info.st_size > MAX_MEMBER_BYTES or len(members) >= MAX_MEMBERS:
                raise IntegrityError("compact evidence limits exceeded: " + relative)
            with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as file:
                opened = os.fstat(file.fileno())
                if (opened.st_ino, opened.st_dev) != (info.st_ino, info.st_dev):
                    raise IntegrityError("file changed identity during capture: " + relative)
                data = file.read(info.st_size)
                after = os.fstat(file.fileno())
            if len(data) != info.st_size:
                raise IntegrityError("file shrank during capture: " + relative)
            if after.st_mtime_ns != info.st_mtime_ns and not relative.startswith("server/") and relative != "server-helper.stdout":
                raise IntegrityError("completed evidence changed during capture: " + relative)
            members[relative] = data
            copies[relative] = {"bytes_copied": len(data), "mtime_ns_observed": info.st_mtime_ns,
                                "size_after_copy": after.st_size, "live_file": relative.startswith("server/")}
            if sum(len(value) for value in members.values()) > MAX_TOTAL_BYTES:
                raise IntegrityError("compact evidence total size limit exceeded")
    members["capture.json"] = encoded({"started_at": started, "finished_at": now(), "raw_root": str(raw_root),
                                        "files": copies, "excluded": sorted(excluded),
                                        "live_capture_note": "server files copied at their initially observed lengths; server remains externally owned"})
    members["collector-source.py"] = Path(__file__).read_bytes()
    return members


def collect(raw_root, out):
    raw_root, out = Path(raw_root).resolve(), Path(out).absolute()
    if out.resolve().is_relative_to(raw_root):
        raise IntegrityError("output directory must be outside the raw evidence root")
    for run in (*RUNS, INVALID, MODEL_LIMIT):
        path = raw_root / run / "result.json"
        if not path.is_file() or path.is_symlink():
            raise IntegrityError("wait for all selected runs and the preserved first attempt: " + str(path))
    members = collect_members(raw_root)
    summary, invalid, model_limit = summaries(members)
    out.mkdir(parents=True, exist_ok=False)
    archive = out / "evidence.tar.gz"
    with archive.open("xb") as output, gzip.GzipFile(fileobj=output, mode="wb", filename="", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w|") as tar:
            for name, data in sorted(members.items()):
                info = tarfile.TarInfo(name)
                info.size = len(data); info.mode = 0o644; info.mtime = 0
                tar.addfile(info, io.BytesIO(data))
    manifest = {"schema": "neural.download.local-worker-evidence.v1", "archive": "evidence.tar.gz",
                "archive_sha256": sha(archive.read_bytes()), "members": {
                    name: {"sha256": sha(data), "bytes": len(data)} for name, data in sorted(members.items())},
                "public_files": public_files(members)}
    for name, member in manifest["public_files"].items():
        path = out / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(members[member])
    (out / "manifest.json").write_bytes(encoded(manifest))
    (out / "summary.json").write_bytes(encoded(summary))
    (out / "invalid-attempt-summary.json").write_bytes(encoded(invalid))
    (out / "model-limit-attempt-summary.json").write_bytes(encoded(model_limit))
    return verify(out)


def verify(out):
    out = Path(out)
    manifest = json.loads((out / "manifest.json").read_text())
    if manifest.get("archive") != "evidence.tar.gz":
        raise IntegrityError("unexpected archive name")
    archive = out / "evidence.tar.gz"
    if sha(archive.read_bytes()) != manifest.get("archive_sha256"):
        raise IntegrityError("archive SHA-256 mismatch")
    members, total = {}, 0
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            path = PurePosixPath(member.name)
            if not member.isfile() or path.is_absolute() or ".." in path.parts or member.name in members:
                raise IntegrityError("unsafe or duplicate archive member")
            if member.size > MAX_MEMBER_BYTES or len(members) >= MAX_MEMBERS:
                raise IntegrityError("archive member limits exceeded")
            total += member.size
            if total > MAX_TOTAL_BYTES:
                raise IntegrityError("archive total limit exceeded")
            data = tar.extractfile(member).read()
            if manifest.get("members", {}).get(member.name) != {"bytes": len(data), "sha256": sha(data)}:
                raise IntegrityError("member hash mismatch: " + member.name)
            members[member.name] = data
    if set(members) != set(manifest.get("members", {})):
        raise IntegrityError("archive and manifest member sets differ")
    projections = public_files(members)
    if projections != manifest.get("public_files"):
        raise IntegrityError("public file map differs from source receipts")
    for name, member in projections.items():
        path = out / name
        if path.is_symlink() or path.parent.is_symlink() or not path.is_file() or path.read_bytes() != members[member]:
            raise IntegrityError("public file differs from archived source: " + name)
    summary, invalid, model_limit = summaries(members)
    if json.loads((out / "summary.json").read_text()) != summary:
        raise IntegrityError("summary differs from archived source receipts")
    if json.loads((out / "invalid-attempt-summary.json").read_text()) != invalid:
        raise IntegrityError("invalid-attempt summary differs from source receipts")
    if json.loads((out / "model-limit-attempt-summary.json").read_text()) != model_limit:
        raise IntegrityError("model-limit summary differs from source receipts")
    return {"verified": True, "archive_sha256": manifest["archive_sha256"], "members": len(members),
            "selected_tasks": summary["selected_tasks"], "accepted_tasks": summary["accepted_tasks"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, default=Path("/mnt/fast-ai/bench-results/local-worker-20260914"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = verify(args.out) if args.verify else collect(args.raw_root, args.out)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
