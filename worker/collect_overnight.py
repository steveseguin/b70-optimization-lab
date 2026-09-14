#!/usr/bin/env python3
"""Hash-bound collection of an explicit, multi-profile worker campaign.

Every attempted directory must be declared in campaign.json. Failed protocol
and task attempts remain evidence. No commands, archived Python, model calls,
or GPU operations are executed by collection or verification.
"""
from __future__ import annotations

import argparse
import gzip
import importlib.util
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import stat
import statistics
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


C = module("overnight_common", HERE / "collect_results.py")
THINKING = module("overnight_thinking", HERE / "stream.py")
PLAIN = module("overnight_plain", ROOT / "experiments/qwen38-27b-b70/scripts/check-fp8-practical-session.py")
METRICS = module("overnight_metrics", ROOT / "experiments/qwen38-27b-b70/scripts/bench-short-prefill.py")
SANDBOX = module("overnight_sandbox_scanner", HERE / "sandbox.py")
IntegrityError = C.IntegrityError
SOURCES = {
    "worker/collect_overnight.py": Path(__file__), "worker/collect_results.py": HERE / "collect_results.py",
    "worker/model.py": HERE / "model.py", "worker/run.py": HERE / "run.py",
    "worker/sandbox.py": HERE / "sandbox.py", "worker/stream.py": HERE / "stream.py",
    "plain-stream.py": ROOT / "experiments/qwen38-27b-b70/scripts/check-fp8-practical-session.py",
    "prefill-metrics.py": ROOT / "experiments/qwen38-27b-b70/scripts/bench-short-prefill.py",
}
REFERENCE = ROOT / "experiments/local-coding-worker/data/2026-09-14-five-issues/summary.json"


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode()


def identifier(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]+", value)


def tree_sha(tree):
    return C.sha(json.dumps(tree, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode())


def validate_campaign(campaign):
    if campaign.get("schema") != "neural.download.worker-overnight-campaign.v1":
        raise IntegrityError("unsupported campaign schema")
    if "review_identity_required" in campaign and type(campaign["review_identity_required"]) is not bool:
        raise IntegrityError("review_identity_required must be boolean")
    profiles, attempts = campaign.get("profiles"), campaign.get("attempts")
    if not isinstance(profiles, dict) or not profiles or not isinstance(attempts, list) or not attempts:
        raise IntegrityError("campaign must explicitly list profiles and every attempt")
    names = set()
    for entry in attempts:
        if (not identifier(entry.get("directory")) or entry["directory"] in names
                or entry.get("profile") not in profiles or not identifier(entry.get("task_id"))
                or entry.get("kind") not in ("task", "protocol")
                or entry.get("role") not in ("target", "control", "heldout", "repeat", "protocol")):
            raise IntegrityError("invalid or duplicate campaign attempt")
        names.add(entry["directory"])
    for key, profile in profiles.items():
        if not identifier(key) or not isinstance(profile.get("config"), dict):
            raise IntegrityError("each named profile must contain its exact config")
    return names


def expected_generation(config):
    generation = dict(config.get("generation", {}))
    thinking = generation.pop("enable_thinking", False)
    effort = generation.pop("reasoning_effort", "low" if thinking else None)
    kwargs = {"enable_thinking": thinking}
    if thinking:
        kwargs.update(reasoning_effort=effort, preserve_thinking=True)
    return kwargs, {"temperature": 0, "top_p": 1, "seed": 42, **generation}


def raw_content_chunks(data):
    chunks = []
    for frame in data.decode().replace("\r\n", "\n").split("\n\n"):
        lines = [line[5:].removeprefix(" ") for line in frame.splitlines() if line.startswith("data:")]
        if not lines:
            continue
        data = "\n".join(lines)
        if data == "[DONE]":
            break
        for choice in json.loads(data).get("choices", []):
            content = (choice.get("delta") or {}).get("content")
            if content:
                chunks.append(content)
    return chunks


def check_timing(response, raw, thinking):
    ids, offsets = response["token_ids"], response.get("token_offsets_s")
    if (not isinstance(offsets, list) or len(offsets) != len(ids)
            or not all(C.finite_number(t) and t >= 0 for t in offsets)
            or offsets != sorted(offsets)):
        raise IntegrityError("invalid complete-output arrival timestamps")
    if response.get("http_ttft_s") != offsets[0]:
        raise IntegrityError("first-token latency does not match first token arrival")
    duration = offsets[-1] - offsets[0]
    expected = (len(ids) - 1) / duration if duration > 0 else None
    actual = response.get("decode_stream_proxy_tokens_s")
    if (expected is None and actual is not None) or (expected is not None and
            (not C.finite_number(actual) or not math.isclose(expected, actual, rel_tol=1e-12))):
        raise IntegrityError("all-output decode proxy does not match token arrival intervals")
    if not C.finite_number(response.get("elapsed_s")) or response["elapsed_s"] < offsets[-1]:
        raise IntegrityError("elapsed response time precedes the final token")
    valid_action = response.get("action_format_valid")
    if type(valid_action) is not bool:
        raise IntegrityError("completed response requires a boolean action-format result")
    if valid_action:
        ready = response.get("action_ready_s")
        if not C.finite_number(ready) or ready < 0 or ready < response["elapsed_s"]:
            raise IntegrityError("action-ready latency must be finite and at or after the complete response")
    elif "action_ready_s" in response:
        raise IntegrityError("invalid action format cannot have an action-ready latency")
    if thinking:
        chunks = raw_content_chunks(raw)
        content_offsets = response.get("content_chunk_offsets_s", [])
        if (len(chunks) != len(content_offsets) or not all(C.finite_number(t) and t >= 0 for t in content_offsets)
                or content_offsets != sorted(content_offsets)):
            raise IntegrityError("invalid final-answer content timestamps")
        answer = response["answer_content"]
        start = len(response["text"]) - len(answer) if response["reasoning_format"] == "inline" else 0
        start += len(answer) - len(answer.lstrip())
        position = 0
        expected_answer = None
        for chunk, offset in zip(chunks, content_offsets):
            if position <= start < position + len(chunk):
                expected_answer = offset
                break
            position += len(chunk)
        if response.get("http_answer_ttft_s") != expected_answer or expected_answer is None:
            raise IntegrityError("first-answer latency does not match the answer boundary")


class Reader:
    def __init__(self, members):
        self.members, self.sources = members, {}
    def data(self, name):
        if name not in self.members:
            raise IntegrityError("missing required evidence: " + name)
        self.sources[name] = C.sha(self.members[name])
        return self.members[name]
    def json(self, name):
        return json.loads(self.data(name))


def review_request(reader, prefix, attempt, config):
    payload = reader.json(prefix + "/request.json")
    kwargs, sampling = expected_generation(config)
    if (payload.get("chat_template_kwargs") != kwargs or any(payload.get(k) != v for k, v in sampling.items())
            or payload.get("model") != config["model"] or payload.get("max_tokens") != config["max_output_tokens"]
            or payload.get("n") != 1 or payload.get("stream") is not True
            or payload.get("return_token_ids") is not True or payload.get("stream_options") != {"include_usage": True}):
        raise IntegrityError("request differs from the declared client profile: " + prefix)
    allowed = {"model", "messages", "chat_template_kwargs", "max_tokens", "n", "stream", "return_token_ids", "stream_options"} | set(sampling)
    if set(payload) != allowed:
        raise IntegrityError("undeclared request options: " + prefix)
    count = reader.json(prefix + "/token-count.json")
    if count.get("input_tokens") != attempt.get("prompt_tokens") or count.get("limit") != config["max_input_tokens"]:
        raise IntegrityError("token-count receipt differs from attempted request: " + prefix)
    raw = reader.data(prefix + "/response.sse") if prefix + "/response.sse" in reader.members else None
    thinking = kwargs["enable_thinking"]
    parsed = None
    parse_error = None
    if raw is not None:
        try:
            parser = THINKING if thinking else PLAIN
            parsed = parser.consume_stream(io.BytesIO(raw), io.BytesIO(), 0, clock=lambda: 0)
        except Exception as exc:
            parse_error = type(exc).__name__ + ": " + str(exc)
    completed = attempt.get("status") == "completed"
    if not completed:
        return {"directory": attempt["directory"], "status": attempt.get("status"), "error": attempt.get("error"),
                "raw_stream_present": raw is not None, "stream_parser_error": parse_error,
                "parsed_prompt_tokens": parsed.get("prompt_tokens") if parsed else None,
                "tokenizer_matches_stream": parsed["prompt_tokens"] == count["input_tokens"] if parsed else None,
                "metrics_included": False}, payload, None
    if parsed is None:
        raise IntegrityError("completed request has no valid full stream: " + prefix + " " + str(parse_error))
    response = reader.json(prefix + "/response.json")
    structural = ["text", "text_sha256", "token_ids", "token_ids_available", "usage", "prompt_tokens",
                  "completion_tokens", "cached_tokens", "finish_reasons", "response_ids"]
    if thinking:
        structural += ["answer_content", "reasoning_content", "reasoning_format"]
    if any(response.get(key) != parsed.get(key) for key in structural):
        raise IntegrityError("response differs from raw stream interpretation: " + prefix)
    if not response["token_ids"] or len(response["token_ids"]) != response["completion_tokens"]:
        raise IntegrityError("full output token IDs are required: " + prefix)
    if response["prompt_tokens"] != count["input_tokens"]:
        raise IntegrityError("tokenizer and generation input counts differ: " + prefix)
    check_timing(response, raw, thinking)
    measured = METRICS.metric_delta(reader.data(prefix + "/metrics-before.txt").decode(),
                                   reader.data(prefix + "/metrics-after.txt").decode(), response["prompt_tokens"])
    if any(response.get(key) != value for key, value in measured.items()):
        raise IntegrityError("prefill counters differ from stored measurement: " + prefix)
    mapping = {"prompt_tokens": "prompt_tokens", "completion_tokens": "completion_tokens", "http_ttft_s": "http_ttft_s",
               "server_prefill_s": "server_prefill_s", "server_prefill_tokens_s": "server_prefill_tokens_per_s",
               "decode_stream_proxy_tokens_s": "decode_stream_proxy_tokens_s", "elapsed_s": "elapsed_s"}
    if any(attempt.get(key) != response.get(value) for key, value in mapping.items()):
        raise IntegrityError("request summary differs from response: " + prefix)
    if "generation_profile" in response and response["generation_profile"] != {"chat_template_kwargs": kwargs, "sampling": sampling}:
        raise IntegrityError("generation-profile receipt differs from declared profile: " + prefix)
    row = {**attempt, "metrics_included": True, "all_output_includes_reasoning": thinking,
           "http_answer_ttft_s": response.get("http_answer_ttft_s") if thinking else response["http_ttft_s"],
           "action_ready_s": response.get("action_ready_s"), "cached_tokens": 0,
           "token_ids_sha256": C.sha(json.dumps(response["token_ids"], separators=(",", ":")).encode()),
           "text_sha256": response["text_sha256"], "reasoning_format": response.get("reasoning_format")}
    return row, payload, response


def review_task(reader, directory, result, config, entry, review_identity_required=False):
    required = ["task.json", "baseline-validation.json", "sandbox.json", "snapshot.json", "runner-identity.json"]
    missing = [name for name in required if directory + "/" + name not in reader.members]
    if missing:
        if result.get("acceptance_passed"):
            raise IntegrityError("claimed task acceptance is missing execution receipts: " + directory)
        return {"acceptance_supported": False, "evidence_gaps": missing, "human_review": "pending"}
    task = reader.json(directory + "/task.json")
    command = task.get("validation_command")
    args = shlex.split(command) if isinstance(command, str) else []
    if (len(args) != 2 or args[0] not in ("node", "python3", "python")
            or not args[1].startswith("/acceptance/") or len(PurePosixPath(args[1]).parts) != 3):
        raise IntegrityError("task validation command does not name one frozen acceptance script: " + directory)
    acceptance_name = PurePosixPath(args[1]).name
    acceptance_path = "sources/worker/acceptance/" + acceptance_name
    acceptance_bytes = reader.data(acceptance_path)
    acceptance_sha = C.sha(acceptance_bytes)
    if reader.data("harness-acceptance/" + acceptance_name) != reader.data(acceptance_path):
        raise IntegrityError("acceptance source copy differs from the campaign fixture snapshot")
    acceptance_manifest = reader.json("harness-acceptance/manifest.json")
    if acceptance_manifest.get("files", {}).get(acceptance_name) != {"bytes": len(acceptance_bytes), "sha256": acceptance_sha}:
        raise IntegrityError("acceptance fixture differs from the frozen campaign manifest")
    baseline = reader.json(directory + "/baseline-validation.json")
    sandbox = reader.json(directory + "/sandbox.json")
    snapshot = reader.json(directory + "/snapshot.json")
    identity = reader.json(directory + "/runner-identity.json")
    if result.get("source_commit") != snapshot.get("source_commit") or identity.get("source_commit") != snapshot.get("source_commit"):
        raise IntegrityError("source-commit bindings disagree: " + directory)
    if task.get("source_commit") != result.get("source_commit"):
        raise IntegrityError("task source commit differs from actual source: " + directory)
    for field, source in (("runner_sha256", "worker/run.py"), ("model_adapter_sha256", "worker/model.py"),
                          ("sandbox_sha256", "worker/sandbox.py")):
        if identity.get(field) != C.sha(reader.data("sources/" + source)):
            raise IntegrityError("runner source identity mismatch: " + directory + " " + field)
    if config.get("generation", {}).get("enable_thinking") and identity.get("thinking_stream_sha256") != C.sha(reader.data("sources/worker/stream.py")):
        raise IntegrityError("thinking-parser identity mismatch: " + directory)
    if identity.get("generation", {}) != config.get("generation", {}) or identity.get("observation_format", "json") != config.get("observation_format", "json"):
        raise IntegrityError("runner profile binding mismatch: " + directory)
    expected = task.get("expected_baseline_error")
    baseline_ok = (not task.get("expected_baseline_failure") or (baseline.get("returncode") not in (None, 0)
                   and isinstance(expected, str) and expected and expected in baseline.get("output", "")))
    patch = result.get("patch")
    final_tree = None
    if patch:
        if patch != reader.json(directory + "/changes.json") or patch.get("patch_sha256") != C.sha(reader.data(directory + "/changes.patch")):
            raise IntegrityError("patch receipt mismatch: " + directory)
        if patch.get("source_commit") != snapshot.get("source_commit") or patch.get("source_archive_sha256") != snapshot.get("source_archive_sha256"):
            raise IntegrityError("patch source snapshot mismatch: " + directory)
        tree = dict(snapshot["baseline"])
        seen = set()
        for change in patch.get("changed_files", []):
            name = change["path"]
            if name in seen or tree.get(name) != change.get("before"):
                raise IntegrityError("changed-file baseline binding mismatch: " + directory)
            seen.add(name)
            if change.get("after") is None:
                tree.pop(name, None)
            else:
                tree[name] = change["after"]
        final_tree = tree_sha(tree)
    freeze_path = directory + "/freeze-check.json"
    freeze = reader.json(freeze_path) if freeze_path in reader.members else None
    if freeze and freeze.get("checked"):
        if (freeze.get("baseline_tree_sha256") != tree_sha(snapshot["baseline"])
                or freeze.get("snapshot_baseline_sha256") != tree_sha(snapshot["baseline"])
                or (patch and freeze.get("workspace_tree_sha256") != final_tree)
                or freeze.get("changed_files_match") is not True or freeze.get("cpu_sandbox_recorded_stopped") is not True):
            raise IntegrityError("initial filesystem freeze differs from archived baseline/change receipts: " + directory)
    paths = sorted((name for name in reader.members if name.startswith(directory + "/validation-") and name.endswith(".json")),
                   key=lambda name: int(name.rsplit("-", 1)[-1].split(".")[0]))
    validations = [reader.json(name) for name in paths]
    accepted = bool(result.get("acceptance_passed") and result.get("agent_result", {}).get("exit_status") == "Submitted"
                    and baseline_ok and snapshot.get("source_state", {}).get("clean") is True and sandbox.get("stopped") is True
                    and patch and patch.get("changed_files") and patch.get("source_repo_unchanged") is True
                    and patch.get("baseline_unchanged") is True and validations and validations[-1].get("accepted") is True
                    and validations[-1].get("returncode") == 0 and validations[-1].get("workspace_stable") is True
                    and result.get("final_workspace_matches_acceptance") is True
                    and result.get("acceptance_tree_sha256") == final_tree == result.get("final_workspace_tree_sha256")
                    and validations[-1].get("workspace_before_sha256") == final_tree == validations[-1].get("workspace_after_sha256")
                    and freeze and freeze.get("checked") is True)
    if result.get("acceptance_passed") and not accepted:
        raise IntegrityError("claimed task acceptance lacks matching baseline/final-tree/teardown evidence: " + directory)
    review_path = directory + "/independent-review.json"
    review = reader.json(review_path) if review_path in reader.members else None
    if review is not None:
        if not isinstance(review, dict) or review.get("task_id") != result.get("task_id"):
            raise IntegrityError("independent review identifies a different task: " + directory)
        if review.get("attempt") != entry["profile"]:
            raise IntegrityError("independent review attempt differs from the campaign profile: " + directory)
        bindings = {"attempt_directory": entry["directory"],
                    "patch_sha256": patch.get("patch_sha256") if patch else None,
                    "final_workspace_tree_sha256": final_tree,
                    "source_commit": snapshot.get("source_commit"),
                    "model_adapter_sha256": identity.get("model_adapter_sha256")}
        for field, expected_binding in bindings.items():
            if review_identity_required and field not in review:
                raise IntegrityError("independent review is missing required identity binding " + field + ": " + directory)
            if field in review and review[field] != expected_binding:
                raise IntegrityError("independent review identity binding differs for " + field + ": " + directory)
    verdict = review.get("verdict") if review else None
    review_status = "approved" if verdict == "approved-for-human-merge" and accepted else "rejected" if verdict == "rejected" else "pending"
    return {"acceptance_supported": accepted, "baseline_matches_expected_failure": bool(baseline_ok),
            "baseline_returncode": baseline.get("returncode"), "expected_baseline_error": expected,
            "cpu_sandbox_recorded_stopped": sandbox.get("stopped") is True, "derived_final_tree_sha256": final_tree,
            "baseline_tree_sha256": tree_sha(snapshot["baseline"]), "filesystem_freeze": freeze,
            "acceptance_fixture": {"command": command, "source": acceptance_path, "sha256": acceptance_sha,
                                   "snapshot_scope": acceptance_manifest.get("scope"),
                                   "scope": "frozen campaign fixture snapshot; source bytes retained separately from future acceptance revisions"},
            "patch_sha256": patch.get("patch_sha256") if patch else None,
            "independent_review": review, "independent_review_status": review_status, "human_review": "pending"}


def aggregate(rows):
    completed = [row for row in rows if row.get("metrics_included")]
    result = C.aggregate(completed)
    for field in ("http_answer_ttft_s", "action_ready_s"):
        values = [row[field] for row in completed if C.finite_number(row.get(field))]
        result[field] = {"median": statistics.median(values) if values else None, "measured_calls": len(values)}
    result["output_token_total_including_reasoning"] = sum(row["completion_tokens"] for row in completed)
    return result


def summarize(members):
    reader = Reader(members)
    campaign = reader.json("campaign.json")
    declared = validate_campaign(campaign)
    observed = {name.split("/", 1)[0] for name in members if name.endswith("/result.json") and name.count("/") == 1}
    if observed != declared:
        raise IntegrityError("declared attempts and archived result directories differ")
    reference = reader.json("reference/original-summary.json")
    if reference.get("accepted_tasks") != 3 or reference.get("selected_tasks") != 5:
        raise IntegrityError("original reference is not the frozen three-of-five trial")
    attempts, groups, projections = [], {}, {}
    for entry in campaign["attempts"]:
        directory = entry["directory"]
        config = reader.json(directory + "/config.json")
        if config != campaign["profiles"][entry["profile"]]["config"]:
            raise IntegrityError("attempt config differs from declared profile: " + directory)
        result = reader.json(directory + "/result.json")
        if entry["kind"] == "task" and result.get("task_id") != entry["task_id"]:
            raise IntegrityError("task identifier differs from campaign entry: " + directory)
        calls = result.get("requests", [])
        if result.get("model_requests") != len(calls):
            raise IntegrityError("model request count differs from attempts: " + directory)
        trajectory_path = directory + "/trajectory.json"
        trajectory = reader.json(trajectory_path).get("messages", []) if trajectory_path in members else None
        canonical_history = []
        if trajectory is not None:
            for message in trajectory:
                if message.get("role") not in ("system", "user", "assistant"):
                    continue
                clean = {"role": message["role"], "content": message["content"]}
                if config.get("generation", {}).get("enable_thinking") and message["role"] == "assistant":
                    clean["reasoning"] = message.get("reasoning_content", "")
                canonical_history.append(clean)
        requests, previous, previous_response, seen = [], None, None, set()
        for call in calls:
            number = call.get("directory")
            if not isinstance(number, str) or not number.isdigit() or number in seen:
                raise IntegrityError("duplicate/invalid request directory: " + directory)
            seen.add(number)
            prefix = directory + "/requests/" + number
            if reader.json(prefix + "/attempt.json") != call:
                raise IntegrityError("attempt receipt differs from task result: " + prefix)
            row, payload, response = review_request(reader, prefix, call, config)
            history = payload.get("messages")
            if not isinstance(history, list) or not history:
                raise IntegrityError("missing model conversation history: " + prefix)
            history_errors = []
            if trajectory is not None and history != canonical_history[:len(history)]:
                history_errors.append("request history differs from the complete archived trajectory")
            if previous is not None:
                if len(history) <= len(previous) or history[:len(previous)] != previous:
                    history_errors.append("conversation prefix was dropped or changed")
                # Legacy non-thinking FormatError recovery omits the malformed
                # assistant turn. Thinking recovery preserves that turn and its
                # reasoning; trajectory and prefix checks still cover both paths.
                thinking = config.get("generation", {}).get("enable_thinking")
                require_assistant = (previous_response
                    and ("action_ready_s" in previous_response or "action_format_valid" in previous_response)
                    and (thinking or previous_response.get("action_format_valid") is not False))
                if require_assistant:
                    expected = {"role": "assistant", "content": previous_response.get("answer_content", previous_response["text"])}
                    if config.get("generation", {}).get("enable_thinking"):
                        expected["reasoning"] = previous_response["reasoning_content"]
                    if len(history) <= len(previous) or history[len(previous)] != expected:
                        history_errors.append("previous assistant reasoning/answer was not preserved with canonical fields")
            if config.get("generation", {}).get("enable_thinking") and any(message.get("role") == "assistant" and not isinstance(message.get("reasoning"), str) for message in history):
                history_errors.append("thinking assistant history omitted canonical reasoning field")
            if history_errors and call.get("status") == "completed":
                raise IntegrityError("; ".join(history_errors) + ": " + prefix)
            row["history_errors"] = history_errors
            previous, previous_response = history, response
            requests.append(row)
        wire_directories = {name.split("/")[2] for name in members if name.startswith(directory + "/requests/") and name.endswith("/request.json")}
        if wire_directories != seen:
            raise IntegrityError("generation request files are missing from the attempt ledger: " + directory)
        capture_info = reader.json("capture.json")
        recorded_directories = {name.split("/")[2] for name in capture_info.get("directories", [])
                                if name.startswith(directory + "/requests/") and len(name.split("/")) == 3}
        pre_generation = []
        for number in sorted(recorded_directories - seen):
            prefix = directory + "/requests/" + number + "/"
            files = sorted(name for name in members if name.startswith(prefix))
            if prefix + "attempt.json" in members or prefix + "response.sse" in members:
                raise IntegrityError("unlisted generation evidence in request directory: " + prefix)
            pre_generation.append({"directory": number, "status": "pre-generation only; no generation request recorded", "files": files})
        if entry["kind"] == "task":
            checks = review_task(reader, directory, result, config, entry, campaign.get("review_identity_required", False))
        else:
            supported = result.get("status") == "passed" and bool(requests) and all(row["metrics_included"] for row in requests) and result.get("no_commands_executed") is True
            if result.get("status") == "passed" and not supported:
                raise IntegrityError("claimed protocol success lacks complete streams/no-command receipt")
            checks = {"protocol_supported": supported, "acceptance_supported": False,
                      "no_commands_executed": result.get("no_commands_executed"), "human_review": "not a coding task"}
        row = {**entry, "recorded_status": result.get("status"), "error": result.get("error"),
               "model_requests": len(calls), "elapsed_seconds": result.get("elapsed_seconds"),
               "profile_sha256": C.sha(encoded(config)),
               "generation": {"chat_template_kwargs": expected_generation(config)[0], "sampling": expected_generation(config)[1]},
               "observation_format": config.get("observation_format", "json"),
               "checks": checks, "requests": requests, "metrics": aggregate(requests)}
        row["pre_generation_directories"] = pre_generation
        attempts.append(row)
        group = groups.setdefault(entry["profile"], {"task_attempts": 0, "accepted_tasks": 0, "incomplete_tasks": 0,
                                                   "reviewed_approved_tasks": 0, "review_rejected_tasks": 0, "review_pending_tasks": 0,
                                                   "protocol_attempts": 0, "tasks": {}, "calls": [], "task_calls": [], "protocol_calls": []})
        if entry["kind"] == "task":
            accepted = checks["acceptance_supported"]
            group["task_attempts"] += 1; group["accepted_tasks"] += int(accepted); group["incomplete_tasks"] += int(not accepted)
            review_status = checks.get("independent_review_status", "pending")
            counter = {"approved": "reviewed_approved_tasks", "rejected": "review_rejected_tasks", "pending": "review_pending_tasks"}[review_status]
            group[counter] += 1
            group["tasks"].setdefault(entry["task_id"], []).append({"directory": directory, "role": entry["role"], "automatic_acceptance": accepted,
                                                                  "independent_review": review_status})
            group["task_calls"].extend(requests)
        else:
            group["protocol_attempts"] += 1
            group["protocol_calls"].extend(requests)
        group["calls"].extend(requests)
        for folder, extension, member in (("patches", ".patch", directory + "/changes.patch"), ("reviews", ".md", directory + "/independent-review.md")):
            if members.get(member):
                projections[folder + "/" + directory + extension] = member
    for group in groups.values():
        group["accepted_tasks_definition"] = "automatic bounded acceptance only; reviewed_approved_tasks additionally requires independent patch approval"
        group["all_calls_metrics"] = aggregate(group.pop("calls"))
        group["metrics"] = aggregate(group.pop("task_calls"))
        group["protocol_metrics"] = aggregate(group.pop("protocol_calls"))
    summary = {"schema": "neural.download.local-worker-overnight-summary.v1", "attempts": attempts, "profiles": groups,
               "reference": {"label": "original five-issue trial; separate reference, not added to new-profile counts",
                             "accepted_tasks": 3, "tasks": 5, "summary_sha256": C.sha(reader.data("reference/original-summary.json"))},
               "capture": reader.json("capture.json"), "public_files": projections,
               "metric_scope": "all generated tokens, including reasoning; completed streams only; first-token and first-answer latency reported separately; no answer-only throughput",
               "quality_scope": "recorded task acceptance and independent review; no broad coding benchmark, exact-output qualification, or speed promotion",
               "human_review": "pending; patches are candidates, including partial patches from incomplete tasks",
               "source_checks": reader.sources}
    return summary


def freeze_workspace(raw_root, entry):
    directory = raw_root / entry["directory"]
    required = [directory / name for name in ("snapshot.json", "sandbox.json", "baseline", "workspace")]
    if not all(path.exists() and not path.is_symlink() for path in required):
        return {"checked": False, "reason": "baseline/workspace or execution receipts unavailable"}
    sandbox = json.loads((directory / "sandbox.json").read_text())
    if sandbox.get("stopped") is not True:
        return {"checked": False, "reason": "CPU sandbox is not recorded stopped"}
    snapshot = json.loads((directory / "snapshot.json").read_text())
    baseline = SANDBOX._regular_tree(directory / "baseline")
    workspace = SANDBOX._regular_tree(directory / "workspace")
    if baseline != snapshot["baseline"]:
        raise IntegrityError("actual baseline differs from source snapshot: " + entry["directory"])
    changes_path = directory / "changes.json"
    changed_files_match = True
    if changes_path.exists():
        changes = json.loads(changes_path.read_text())
        expected = dict(baseline)
        for row in changes.get("changed_files", []):
            name = row["path"]
            if baseline.get(name) != row.get("before") or workspace.get(name) != row.get("after"):
                changed_files_match = False
            if row.get("after") is None:
                expected.pop(name, None)
            else:
                expected[name] = row["after"]
        if expected != workspace:
            changed_files_match = False
    elif workspace != baseline:
        changed_files_match = False
    if not changed_files_match:
        raise IntegrityError("actual workspace differs from exported change manifest: " + entry["directory"])
    return {"checked": True, "captured_at": C.now(), "cpu_sandbox_recorded_stopped": True,
            "baseline_tree_sha256": tree_sha(baseline), "snapshot_baseline_sha256": tree_sha(snapshot["baseline"]),
            "workspace_tree_sha256": tree_sha(workspace), "changed_files_match": True,
            "scope": "bounded read-only inventory of stopped CPU sandbox files at initial packet capture"}


def capture(raw_root, campaign):
    declared = validate_campaign(campaign)
    observed = {path.name for path in raw_root.iterdir() if path.is_dir() and ((path / "result.json").exists() or (path / "requests").exists())}
    if observed != declared:
        raise IntegrityError("campaign must list every attempted directory, including unfinished/failed attempts")
    started = C.now(); members = {}; records = {}; excluded = []; recorded_dirs = []; total = 0
    for directory, dirs, files in os.walk(raw_root, followlinks=False):
        parent = Path(directory)
        if parent != raw_root:
            recorded_dirs.append(parent.relative_to(raw_root).as_posix())
        for name in list(dirs):
            path = parent / name
            if path.is_symlink() or name in C.EXCLUDED_DIRS:
                dirs.remove(name); excluded.append(path.relative_to(raw_root).as_posix())
        for name in sorted(files):
            path = parent / name; relative = path.relative_to(raw_root).as_posix(); info = path.lstat()
            if name in C.EXCLUDED_FILES or not stat.S_ISREG(info.st_mode):
                excluded.append(relative); continue
            if info.st_size > C.MAX_MEMBER_BYTES or len(members) >= C.MAX_MEMBERS:
                raise IntegrityError("compact evidence limit exceeded: " + relative)
            with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as file:
                opened = os.fstat(file.fileno())
                if (opened.st_ino, opened.st_dev) != (info.st_ino, info.st_dev):
                    raise IntegrityError("file identity changed while capturing: " + relative)
                data = file.read(info.st_size); after = os.fstat(file.fileno())
            live = relative.startswith("server/")
            if len(data) != info.st_size or (after.st_mtime_ns != info.st_mtime_ns and not live):
                raise IntegrityError("completed evidence changed while capturing: " + relative)
            total += len(data)
            if total > C.MAX_TOTAL_BYTES:
                raise IntegrityError("compact evidence total size limit exceeded")
            members[relative] = data
            records[relative] = {"bytes": len(data), "mtime_ns": info.st_mtime_ns, "live_capture": live, "size_after": after.st_size}
    for entry in campaign["attempts"]:
        if entry["kind"] == "task":
            members[entry["directory"] + "/freeze-check.json"] = encoded(freeze_workspace(raw_root, entry))
    members["campaign.json"] = encoded(campaign)
    members["capture.json"] = encoded({"started_at": started, "finished_at": C.now(), "files": records,
                                           "directories": sorted(recorded_dirs), "excluded": sorted(excluded),
                                           "server_scope": "timestamped live-file copy; no stop or postflight inferred"})
    for name, path in SOURCES.items():
        members["sources/" + name] = path.read_bytes()
    for name, data in list(members.items()):
        if name.startswith("harness-acceptance/"):
            relative = PurePosixPath(name).relative_to("harness-acceptance")
            members["sources/worker/acceptance/" + str(relative)] = data
    members["reference/original-summary.json"] = REFERENCE.read_bytes()
    return members


def collect(raw_root, campaign_path, out):
    raw_root, out = Path(raw_root).resolve(), Path(out).absolute()
    if out.resolve().is_relative_to(raw_root):
        raise IntegrityError("output must be outside the raw evidence root")
    campaign = json.loads(Path(campaign_path).read_text())
    members = capture(raw_root, campaign)
    summary = summarize(members)
    out.mkdir(parents=True, exist_ok=False)
    archive = out / "evidence.tar.gz"
    with archive.open("xb") as file, gzip.GzipFile(fileobj=file, mode="wb", filename="", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w|") as tar:
            for name, data in sorted(members.items()):
                info = tarfile.TarInfo(name); info.size = len(data); info.mode = 0o644; info.mtime = 0
                tar.addfile(info, io.BytesIO(data))
    manifest = {"schema": "neural.download.local-worker-overnight-evidence.v1", "archive_sha256": C.sha(archive.read_bytes()),
                "members": {name: {"bytes": len(data), "sha256": C.sha(data)} for name, data in sorted(members.items())},
                "verifier_sources": {name: C.sha(path.read_bytes()) for name, path in SOURCES.items()},
                "public_files": summary["public_files"]}
    for name, member in summary["public_files"].items():
        path = out / name; path.parent.mkdir(exist_ok=True); path.write_bytes(members[member])
    (out / "manifest.json").write_bytes(encoded(manifest)); (out / "summary.json").write_bytes(encoded(summary))
    return verify(out)


def verify(out):
    out = Path(out); manifest = json.loads((out / "manifest.json").read_text()); archive = out / "evidence.tar.gz"
    if C.sha(archive.read_bytes()) != manifest.get("archive_sha256"):
        raise IntegrityError("archive SHA-256 mismatch")
    if set(manifest.get("verifier_sources", {})) != set(SOURCES):
        raise IntegrityError("archived source inventory is incomplete")
    members, total = {}, 0
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            path = PurePosixPath(member.name)
            if (not member.isfile() or path.is_absolute() or ".." in path.parts or member.name in members
                    or member.size > C.MAX_MEMBER_BYTES or len(members) >= C.MAX_MEMBERS):
                raise IntegrityError("unsafe archive member")
            total += member.size
            if total > C.MAX_TOTAL_BYTES:
                raise IntegrityError("archive size limit exceeded")
            data = tar.extractfile(member).read()
            if manifest.get("members", {}).get(member.name) != {"bytes": len(data), "sha256": C.sha(data)}:
                raise IntegrityError("archive member hash mismatch: " + member.name)
            members[member.name] = data
    if set(members) != set(manifest.get("members", {})):
        raise IntegrityError("archive/manifest member sets differ")
    for name, digest in manifest["verifier_sources"].items():
        if C.sha(members.get("sources/" + name, b"")) != digest:
            raise IntegrityError("archived verifier source mismatch: " + name)
    summary = summarize(members)
    if json.loads((out / "summary.json").read_text()) != summary or manifest.get("public_files") != summary["public_files"]:
        raise IntegrityError("summary/public map differs from archived evidence")
    for name, member in summary["public_files"].items():
        path = out / name
        if path.is_symlink() or path.parent.is_symlink() or not path.is_file() or path.read_bytes() != members[member]:
            raise IntegrityError("public copy differs from archived evidence: " + name)
    return {"verified": True, "attempts": len(summary["attempts"]), "members": len(members),
            "archive_sha256": manifest["archive_sha256"],
            "current_verifier_sources": {name: C.sha(path.read_bytes()) for name, path in SOURCES.items()
                                         if name not in ("worker/model.py", "worker/run.py", "worker/sandbox.py")}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, default=Path("/mnt/fast-ai/bench-results/local-worker-overnight-20260914"))
    parser.add_argument("--campaign", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        result = verify(args.out)
    else:
        result = collect(args.raw_root, args.campaign or args.raw_root / "campaign.json", args.out)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
