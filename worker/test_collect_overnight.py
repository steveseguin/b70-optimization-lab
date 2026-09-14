"""CPU fixtures for complete, failed and multi-profile campaign evidence."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("overnight", Path(__file__).with_name("collect_overnight.py"))
O = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(O)


class OvernightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.raw = self.root / "raw"; self.raw.mkdir(); self.out = self.root / "packet"
        self.config = {"model": "fixture", "max_input_tokens": 28000, "max_output_tokens": 4096,
                       "generation": {"enable_thinking": True, "reasoning_effort": "low", "temperature": 1, "seed": 42}}
        self.campaign = {"schema": "neural.download.worker-overnight-campaign.v1",
                         "profiles": {"thinking-low": {"config": self.config}}, "attempts": []}
        self.reference = self.root / "reference.json"; self.reference.write_bytes(O.C.encoded({"accepted_tasks": 3, "selected_tasks": 5}))

    def write(self, name, value):
        path = self.raw / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(O.C.encoded(value))

    def request(self, directory, number="001", history=None, failed=False, config=None, content_parts=None):
        config = config or self.config
        prefix = directory + "/requests/" + number
        kwargs, sampling = O.expected_generation(config)
        payload = {"model": config["model"], "messages": history or [{"role": "user", "content": "Fixture task"}],
                   "chat_template_kwargs": kwargs, **sampling, "max_tokens": config["max_output_tokens"], "n": 1,
                   "stream": True, "stream_options": {"include_usage": True}, "return_token_ids": True}
        self.write(prefix + "/request.json", payload); self.write(prefix + "/token-count.json", {"input_tokens": 100, "limit": 28000})
        content = ["Consider the issue.", "</think>\n```bash\necho ok\n```"] if kwargs["enable_thinking"] else ["```bash\n", "echo ok\n```"]
        if content_parts is not None: content = content_parts
        events = [{"choices": [{"index": 0, "token_ids": [10 + i], "delta": {"content": text}}]} for i, text in enumerate(content)]
        events += [{"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
                   {"choices": [], "usage": {"prompt_tokens": 100, "completion_tokens": 2, "prompt_tokens_details": {"cached_tokens": 0}}}]
        data = b"".join(("data: " + json.dumps(event) + "\n\n").encode() for event in events) + b"data: [DONE]\n\n"
        (self.raw / prefix / "response.sse").write_bytes(data if not failed else data.replace(b"data: [DONE]\n\n", b""))
        if failed:
            call = {"directory": number, "status": "failed", "prompt_tokens": 100, "error": "ValueError: truncated stream"}
            self.write(prefix + "/attempt.json", call)
            return call, None
        parser = O.THINKING if kwargs["enable_thinking"] else O.PLAIN
        response = parser.consume_stream(io.BytesIO(data), io.BytesIO(), 0, clock=lambda: 0)
        response.update(token_offsets_s=[0.1, 0.2], content_chunk_offsets_s=[0.1, 0.2], http_ttft_s=0.1,
                        decode_stream_proxy_tokens_s=10, elapsed_s=0.25, action_ready_s=0.3, action_format_valid=True,
                        generation_profile={"chat_template_kwargs": kwargs, "sampling": sampling})
        if kwargs["enable_thinking"]: response["http_answer_ttft_s"] = 0.2
        before = "vllm:request_prefill_time_seconds_count 0\nvllm:request_prefill_time_seconds_sum 0\nvllm:prompt_tokens_total 0\n"
        after = "vllm:request_prefill_time_seconds_count 1\nvllm:request_prefill_time_seconds_sum 0.08\nvllm:prompt_tokens_total 100\n"
        (self.raw / prefix / "metrics-before.txt").write_text(before); (self.raw / prefix / "metrics-after.txt").write_text(after)
        response.update(O.METRICS.metric_delta(before, after, 100)); self.write(prefix + "/response.json", response)
        call = {"directory": number, "status": "completed", "prompt_tokens": 100, "completion_tokens": 2,
                "http_ttft_s": 0.1, "server_prefill_s": 0.08, "server_prefill_tokens_s": 1250,
                "decode_stream_proxy_tokens_s": 10, "elapsed_s": 0.25}
        self.write(prefix + "/attempt.json", call)
        return call, response

    def protocol(self, directory="protocol", failed=False):
        call, _ = self.request(directory, failed=failed)
        self.write(directory + "/config.json", self.config)
        self.write(directory + "/result.json", {"kind": "protocol", "status": "failed" if failed else "passed",
                   "model_requests": 1, "requests": [call], "no_commands_executed": True})
        self.campaign["attempts"].append({"directory": directory, "task_id": directory, "kind": "protocol", "role": "protocol", "profile": "thinking-low"})

    def task(self):
        directory = "thinking-low-fixture"; call, _ = self.request(directory)
        for name, content in (("baseline", b"before\n"), ("workspace", b"after\n")):
            path = self.raw / directory / name; path.mkdir(); (path / "answer.py").write_bytes(content)
        baseline = {"answer.py": {"sha256": O.C.sha(b"before\n"), "bytes": 7, "mode": "100644"}}
        changed = {"sha256": O.C.sha(b"after\n"), "bytes": 6, "mode": "100644"}; final = O.tree_sha({"answer.py": changed})
        source_commit = "c" * 40; archive_sha = "d" * 64
        patch_bytes = b"fixture patch"
        changes = {"source_commit": source_commit, "source_archive_sha256": archive_sha, "source_repo_unchanged": True,
                   "baseline_unchanged": True, "patch_sha256": O.C.sha(patch_bytes),
                   "changed_files": [{"path": "answer.py", "before": baseline["answer.py"], "after": changed}]}
        self.write(directory + "/config.json", self.config)
        acceptance = self.raw / "harness-acceptance"; acceptance.mkdir(exist_ok=True); (acceptance / "fixture.py").write_text("assert True\n")
        self.write("harness-acceptance/manifest.json", {"files": {"fixture.py": {"bytes": len(b"assert True\n"), "sha256": O.C.sha(b"assert True\n")}}})
        self.write(directory + "/task.json", {"id": "fixture", "source_commit": source_commit, "expected_baseline_failure": True,
                                              "expected_baseline_error": "known failure", "validation_command": "python3 /acceptance/fixture.py"})
        self.write(directory + "/baseline-validation.json", {"returncode": 1, "output": "known failure"})
        self.write(directory + "/sandbox.json", {"stopped": True})
        self.write(directory + "/snapshot.json", {"source_commit": source_commit, "source_archive_sha256": archive_sha, "baseline": baseline, "source_state": {"clean": True}})
        self.write(directory + "/changes.json", changes); (self.raw / directory / "changes.patch").write_bytes(patch_bytes)
        self.write(directory + "/validation-1.json", {"accepted": True, "returncode": 0, "workspace_stable": True,
                                                     "workspace_before_sha256": final, "workspace_after_sha256": final})
        identity = {"source_commit": source_commit, "generation": self.config["generation"], "observation_format": "json"}
        for field, name in (("runner_sha256", "worker/run.py"), ("model_adapter_sha256", "worker/model.py"),
                            ("sandbox_sha256", "worker/sandbox.py"), ("thinking_stream_sha256", "worker/stream.py")):
            identity[field] = O.C.sha(O.SOURCES[name].read_bytes())
        self.write(directory + "/runner-identity.json", identity)
        self.write(directory + "/result.json", {"task_id": "fixture", "source_commit": source_commit, "status": "tests-passed-awaiting-review",
                   "model_requests": 1, "requests": [call], "acceptance_passed": True, "agent_result": {"exit_status": "Submitted"},
                   "patch": changes, "final_workspace_matches_acceptance": True, "acceptance_tree_sha256": final, "final_workspace_tree_sha256": final})
        self.campaign["attempts"].append({"directory": directory, "task_id": "fixture", "kind": "task", "role": "target", "profile": "thinking-low"})
        return directory

    def members(self):
        self.write("campaign.json", self.campaign)
        with patch.object(O, "REFERENCE", self.reference): return O.capture(self.raw, self.campaign)

    def collect(self):
        self.write("campaign.json", self.campaign)
        with patch.object(O, "REFERENCE", self.reference): return O.collect(self.raw, self.raw / "campaign.json", self.out)

    def test_task_and_failed_protocol_roundtrip(self):
        self.task(); self.protocol(failed=True)
        self.assertTrue(self.collect()["verified"])
        summary = json.loads((self.out / "summary.json").read_text())
        self.assertEqual(summary["profiles"]["thinking-low"]["accepted_tasks"], 1)
        self.assertEqual(summary["profiles"]["thinking-low"]["metrics"]["completed_calls"], 1)
        self.assertEqual(summary["attempts"][1]["requests"][0]["metrics_included"], False)
        self.assertIn("truncated", summary["attempts"][1]["requests"][0]["stream_parser_error"])

    def test_unlisted_failed_attempt_is_rejected(self):
        self.protocol(); self.write("undeclared/result.json", {"status": "failed"})
        with self.assertRaisesRegex(O.IntegrityError, "every attempted"): self.members()

    def test_profile_override_is_rejected(self):
        self.protocol(); members = self.members()
        payload = json.loads(members["protocol/requests/001/request.json"]); payload["temperature"] = 0
        members["protocol/requests/001/request.json"] = O.C.encoded(payload)
        with self.assertRaisesRegex(O.IntegrityError, "declared client profile"): O.summarize(members)

    def test_reasoning_and_token_tampering_is_rejected(self):
        self.protocol(); members = self.members()
        response = json.loads(members["protocol/requests/001/response.json"]); response["reasoning_content"] = "fabricated"
        members["protocol/requests/001/response.json"] = O.C.encoded(response)
        with self.assertRaisesRegex(O.IntegrityError, "raw stream interpretation"): O.summarize(members)

    def test_answer_latency_is_independently_recomputed(self):
        self.protocol(); members = self.members()
        response = json.loads(members["protocol/requests/001/response.json"]); response["http_answer_ttft_s"] = 0.1
        members["protocol/requests/001/response.json"] = O.C.encoded(response)
        with self.assertRaisesRegex(O.IntegrityError, "first-answer latency"): O.summarize(members)

    def test_acceptance_tree_is_derived_from_baseline_and_changes(self):
        directory = self.task(); members = self.members()
        snapshot = json.loads(members[directory + "/snapshot.json"]); snapshot["baseline"]["hidden.txt"] = {"sha256": "e" * 64, "bytes": 5, "mode": "100644"}
        members[directory + "/snapshot.json"] = O.C.encoded(snapshot)
        with self.assertRaisesRegex(O.IntegrityError, "filesystem freeze"): O.summarize(members)

    def test_empty_pre_generation_directory_is_recorded(self):
        self.protocol(); (self.raw / "protocol/requests/002").mkdir()
        row = O.summarize(self.members())["attempts"][0]
        self.assertEqual(row["pre_generation_directories"][0]["directory"], "002")
        self.assertEqual(row["model_requests"], 1)

    def test_preserved_reasoning_history_passes_and_dropped_history_fails(self):
        self.protocol(); _, response = self.request("protocol")
        history = [{"role": "user", "content": "Fixture task"},
                   {"role": "assistant", "content": response["answer_content"], "reasoning": response["reasoning_content"]},
                   {"role": "user", "content": "Next task"}]
        call, _ = self.request("protocol", "002", history)
        result = json.loads((self.raw / "protocol/result.json").read_text()); result["requests"].append(call); result["model_requests"] = 2
        self.write("protocol/result.json", result)
        members = self.members(); self.assertEqual(O.summarize(members)["attempts"][0]["model_requests"], 2)
        payload = json.loads(members["protocol/requests/002/request.json"]); payload["messages"][1]["reasoning"] = ""
        members["protocol/requests/002/request.json"] = O.C.encoded(payload)
        with self.assertRaisesRegex(O.IntegrityError, "previous assistant reasoning"): O.summarize(members)

    def test_archive_and_summary_tamper_fail(self):
        self.protocol(); self.collect()
        path = self.out / "summary.json"; row = json.loads(path.read_text()); row["reference"]["accepted_tasks"] = 5; path.write_bytes(O.C.encoded(row))
        with self.assertRaisesRegex(O.IntegrityError, "summary/public map"): O.verify(self.out)

    def test_nonthinking_readable_profile_and_seed43_are_distinct(self):
        self.protocol()
        plain = {"model": "fixture", "max_input_tokens": 28000, "max_output_tokens": 2048, "observation_format": "tool_response"}
        self.campaign["profiles"]["readable"] = {"config": plain}
        call, _ = self.request("readable-protocol", config=plain)
        self.write("readable-protocol/config.json", plain)
        self.write("readable-protocol/result.json", {"status": "passed", "model_requests": 1, "requests": [call], "no_commands_executed": True})
        self.campaign["attempts"].append({"directory": "readable-protocol", "task_id": "readable-protocol", "profile": "readable", "kind": "protocol", "role": "protocol"})
        seed43 = json.loads(json.dumps(self.config)); seed43["generation"]["seed"] = 43
        self.campaign["profiles"]["thinking-low-seed43"] = {"config": seed43, "family": "thinking-low"}
        call, _ = self.request("seed43-protocol", config=seed43)
        self.write("seed43-protocol/config.json", seed43)
        self.write("seed43-protocol/result.json", {"status": "passed", "model_requests": 1, "requests": [call], "no_commands_executed": True})
        self.campaign["attempts"].append({"directory": "seed43-protocol", "task_id": "seed43-protocol", "profile": "thinking-low-seed43", "kind": "protocol", "role": "protocol"})
        summary = O.summarize(self.members())
        self.assertEqual(len(summary["profiles"]), 3)
        self.assertEqual(summary["attempts"][1]["requests"][0]["http_answer_ttft_s"], 0.1)
        self.assertFalse(summary["attempts"][1]["requests"][0]["all_output_includes_reasoning"])

    def test_failed_legacy_history_and_tokenizer_mismatch_remain_evidence(self):
        self.protocol(); _, response = self.request("protocol")
        history = [{"role": "user", "content": "Fixture task"},
                   {"role": "assistant", "content": response["answer_content"], "reasoning_content": response["reasoning_content"]},
                   {"role": "user", "content": "Next task"}]
        call, _ = self.request("protocol", "002", history)
        raw = self.raw / "protocol/requests/002/response.sse"
        raw.write_text(raw.read_text().replace('"prompt_tokens": 100', '"prompt_tokens": 105'))
        (self.raw / "protocol/requests/002/response.json").unlink()
        call = {"directory": "002", "status": "failed", "prompt_tokens": 100, "error": "Tokenizer and generation input-token counts disagree"}
        self.write("protocol/requests/002/attempt.json", call)
        result = json.loads((self.raw / "protocol/result.json").read_text()); result["requests"].append(call); result.update(model_requests=2, status="failed")
        self.write("protocol/result.json", result)
        summary = O.summarize(self.members()); failed = summary["attempts"][0]["requests"][1]
        self.assertFalse(failed["tokenizer_matches_stream"])
        self.assertEqual(failed["parsed_prompt_tokens"], 105)
        self.assertTrue(failed["history_errors"])
        self.assertEqual(summary["profiles"]["thinking-low"]["protocol_metrics"]["completed_calls"], 1)

    def test_cached_completed_stream_is_rejected(self):
        self.protocol(); members = self.members()
        name = "protocol/requests/001/response.sse"
        members[name] = members[name].replace(b'"cached_tokens": 0', b'"cached_tokens": 1')
        with self.assertRaisesRegex(O.IntegrityError, "valid full stream"): O.summarize(members)

    def test_portable_verify_survives_routine_runtime_source_changes(self):
        self.task(); self.collect()
        changed = self.root / "new-model.py"; changed.write_text("# a later runtime revision\n")
        with patch.dict(O.SOURCES, {"worker/model.py": changed}):
            self.assertTrue(O.verify(self.out)["verified"])

    def test_initial_freeze_rejects_workspace_change_after_export(self):
        directory = self.task(); (self.raw / directory / "workspace/answer.py").write_text("changed after export\n")
        with self.assertRaisesRegex(O.IntegrityError, "actual workspace differs"): self.collect()

    def test_task_commit_must_match_snapshot(self):
        directory = self.task(); members = self.members()
        task = json.loads(members[directory + "/task.json"]); task["source_commit"] = "wrong"
        members[directory + "/task.json"] = O.encoded(task)
        with self.assertRaisesRegex(O.IntegrityError, "task source commit"): O.summarize(members)

    def test_summary_json_uses_literal_utf8(self):
        self.protocol(); self.campaign["description"] = "préfill — 阅读"
        self.collect()
        self.assertIn("préfill — 阅读".encode(), O.encoded(self.campaign))

    def test_automatic_acceptance_does_not_override_review_rejection(self):
        directory = self.task()
        self.write(directory + "/independent-review.json", {"task_id": "fixture", "verdict": "rejected", "rationale": "stale generated browser cache key"})
        summary = O.summarize(self.members()); group = summary["profiles"]["thinking-low"]
        self.assertEqual(group["accepted_tasks"], 1)
        self.assertEqual(group["reviewed_approved_tasks"], 0)
        self.assertEqual(group["review_rejected_tasks"], 1)
        self.assertEqual(summary["attempts"][0]["checks"]["independent_review_status"], "rejected")

    def test_acceptance_snapshot_must_match_bound_source(self):
        directory = self.task(); members = self.members()
        members["sources/worker/acceptance/fixture.py"] = b"assert False\n"
        with self.assertRaisesRegex(O.IntegrityError, "acceptance source copy differs"): O.summarize(members)

    def test_nonthinking_malformed_reply_uses_legacy_correction_history(self):
        plain = {"model": "fixture", "max_input_tokens": 28000, "max_output_tokens": 2048, "observation_format": "tool_response"}
        self.campaign["profiles"]["readable"] = {"config": plain}
        first, response = self.request("readable-recovery", config=plain,
                                       content_parts=["This answer has no ", "executable command block."])
        response["action_format_valid"] = False; response.pop("action_ready_s")
        self.write("readable-recovery/requests/001/response.json", response)
        history = [{"role": "user", "content": "Fixture task"},
                   {"role": "user", "content": "Return exactly one bash command block."}]
        second, answer = self.request("readable-recovery", "002", history, config=plain)
        self.write("readable-recovery/config.json", plain)
        self.write("readable-recovery/result.json", {"status": "passed", "model_requests": 2,
                                                       "requests": [first, second], "no_commands_executed": True})
        self.write("readable-recovery/trajectory.json", {"messages": history + [{"role": "assistant", "content": answer["text"]}]})
        self.campaign["attempts"].append({"directory": "readable-recovery", "task_id": "readable-recovery",
                                           "profile": "readable", "kind": "protocol", "role": "protocol"})
        members = self.members(); summary = O.summarize(members)
        self.assertTrue(summary["attempts"][0]["checks"]["protocol_supported"])
        self.assertEqual(summary["attempts"][0]["requests"][1]["history_errors"], [])
        # Legacy recovery permits omission of only the malformed assistant;
        # it still must preserve the complete prior user/system prefix.
        payload = json.loads(members["readable-recovery/requests/002/request.json"])
        payload["messages"][0]["content"] = "Changed earlier task"
        members["readable-recovery/requests/002/request.json"] = O.encoded(payload)
        with self.assertRaisesRegex(O.IntegrityError, "conversation prefix was dropped or changed"):
            O.summarize(members)

    def test_thinking_malformed_reply_still_requires_assistant_reasoning(self):
        self.protocol()
        path = "protocol/requests/001/response.json"
        response = json.loads((self.raw / path).read_text())
        response["action_format_valid"] = False; response.pop("action_ready_s")
        self.write(path, response)
        history = [{"role": "user", "content": "Fixture task"},
                   {"role": "user", "content": "Return exactly one bash command block."}]
        second, _ = self.request("protocol", "002", history)
        result = json.loads((self.raw / "protocol/result.json").read_text())
        result["requests"].append(second); result["model_requests"] = 2
        self.write("protocol/result.json", result)
        with self.assertRaisesRegex(O.IntegrityError, "previous assistant reasoning/answer was not preserved"):
            O.summarize(self.members())


if __name__ == "__main__": unittest.main()
