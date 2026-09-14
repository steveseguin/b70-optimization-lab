#!/usr/bin/env python3
"""CPU checks for the bounded FP8 practical-session acceptance client."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("fp8_practical", ROOT / "experiments/qwen38-27b-b70/scripts/check-fp8-practical-session.py")
CLIENT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLIENT)
ANSWERS = {
    "conversation": '{"day":"Saturday","shelter":"B","guests":6,"vegetarian":true}',
    "code": '{"bug":"off_by_one","fixed_expression":"sum( range(1,n+1) )","result_for_n_5":15}',
    "document": '{"project":"Cedar","owner":"Maya Chen","delivery":"2026-10-07","budget_usd":4800,"risks":["supplier delay","rain"]}',
}


def stream(text="{}", cached=0, finish="stop", done=True, ids=True):
    choice = {"index": 0, "delta": {"content": text}, "finish_reason": None}
    if ids:
        choice["token_ids"] = [11, 12]
    events = [{"id": "test", "choices": [choice]},
              {"choices": [{"index": 0, "delta": {}, "finish_reason": finish}]},
              {"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 2,
                 "prompt_tokens_details": {"cached_tokens": cached}}}]
    data = b"".join(("data: " + json.dumps(e) + "\n\n").encode() for e in events)
    return data + (b"data: [DONE]\n\n" if done else b"")


def parse(data):
    raw = io.BytesIO()
    ticks = iter(x / 10 for x in range(1, 100))
    result = CLIENT.consume_stream(io.BytesIO(data), raw, 0, lambda: next(ticks))
    return result, raw.getvalue()


class StreamTests(unittest.TestCase):
    def test_complete_stream_preserves_bytes_and_counts(self):
        data = stream()
        result, raw = parse(data)
        self.assertEqual(raw, data)
        self.assertEqual(result["token_ids"], [11, 12])
        self.assertEqual(result["cached_tokens"], 0)
        self.assertIsNone(result["server_prefill_duration_s"])
        # Both IDs arrived together: a zero-duration chunk cannot yield a rate.
        self.assertIsNone(result["decode_stream_proxy_tokens_s"])

    def test_multiple_chunks_use_intervals_not_token_count(self):
        data = stream()
        original = json.dumps({"id": "test", "choices": [{"index": 0, "delta": {"content": "{}"}, "finish_reason": None, "token_ids": [11, 12]}]}).encode()
        replacement = b'data: {"choices":[{"delta":{"content":"{"},"token_ids":[11]}]}\n\ndata: {"choices":[{"delta":{"content":"}"},"token_ids":[12]}]}'
        data = data.replace(b"data: " + original, replacement)
        result, _ = parse(data)
        duration = result["token_offsets_s"][-1] - result["token_offsets_s"][0]
        self.assertAlmostEqual(result["decode_stream_proxy_tokens_s"], 1 / duration)

    def test_missing_token_ids_are_explicitly_unavailable(self):
        result, _ = parse(stream(ids=False))
        self.assertFalse(result["token_ids_available"])
        self.assertIsNone(result["decode_stream_proxy_tokens_s"])

    def test_truncation_and_cap_are_failures(self):
        for data in (stream(done=False), stream(finish="length")):
            with self.subTest(data=data), self.assertRaises(ValueError):
                parse(data)

    def test_unknown_or_nonzero_cache_is_failure(self):
        for cached in (None, 1, False, "0"):
            with self.subTest(cached=cached), self.assertRaises(ValueError):
                parse(stream(cached=cached))

    def test_partial_ids_and_server_error_are_failures(self):
        for data in (stream().replace(b'"completion_tokens": 2', b'"completion_tokens": 3'),
                     b'data: {"error":{"message":"GPU fault"}}\n\n'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                parse(data)

    def test_raw_error_is_preserved(self):
        data = b'data: {broken}\n\n'
        raw = io.BytesIO()
        with self.assertRaises(ValueError):
            CLIENT.consume_stream(io.BytesIO(data), raw, 0, lambda: 0)
        self.assertEqual(raw.getvalue(), data)

    def test_http_error_body_is_preserved_without_retry(self):
        calls = []
        def opener(req, timeout):
            calls.append(req.full_url)
            raise urllib.error.HTTPError(req.full_url, 500, "failure", {}, io.BytesIO(b"server failed"))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            with self.assertRaises(urllib.error.HTTPError):
                CLIENT.request_one("http://localhost:18124/v1", {}, path, opener)
            self.assertEqual((path / "response.sse").read_bytes(), b"server failed")
        self.assertEqual(calls, ["http://localhost:18124/v1/chat/completions"])


class TaskTests(unittest.TestCase):
    def test_valid_answers_allow_json_key_order_and_code_whitespace(self):
        for task, answer in ANSWERS.items():
            self.assertTrue(CLIENT.check_task(task, answer)["passed"])

    def test_wrong_facts_rejected(self):
        cases = [("conversation", ANSWERS["conversation"].replace('"guests":6', '"guests":4')),
                 ("document", ANSWERS["document"].replace("2026-10-07", "2026-10-04")),
                 ("document", ANSWERS["document"].replace("4800", "5200")),
                 ("code", ANSWERS["code"].replace("n+1", "n")),
                 ("code", ANSWERS["code"].replace("sum( range(1,n+1) )", "__import__('os').system('false')"))]
        for task, answer in cases:
            with self.subTest(task=task, answer=answer), self.assertRaises(ValueError):
                CLIENT.check_task(task, answer)

    def test_duplicate_keys_fences_and_boolean_number_rejected(self):
        for answer in (ANSWERS["conversation"][:-1] + ',"guests":6}',
                       "```json\n" + ANSWERS["conversation"] + "\n```",
                       ANSWERS["conversation"].replace('"vegetarian":true', '"vegetarian":1')):
            with self.subTest(answer=answer), self.assertRaises(ValueError):
                CLIENT.check_task("conversation", answer)


class SessionTests(unittest.TestCase):
    def requester(self, calls, failure_at=None, change_repeat=False):
        def request(base, payload, directory):
            calls.append(payload)
            if len(calls) == failure_at:
                raise ValueError("injected failure")
            task = directory.name.split("-", 1)[1]
            result, _ = parse(stream(ANSWERS[task]))
            if change_repeat and len(calls) == 4:
                result["token_ids"] = [11, 13]
            return result
        return request

    def test_exact_six_sequential_requests_and_repeat_identity(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            summary = CLIENT.run_session("http://localhost", "test", Path(tmp) / "run", self.requester(calls))
        self.assertTrue(summary["passed"])
        self.assertEqual(len(calls), 6)
        self.assertEqual(calls[:3], calls[3:])
        self.assertTrue(summary["all_stream_token_ids_available"])

    def test_failure_stops_next_request_and_writes_summary(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run"
            result = CLIENT.run_session("http://localhost", "test", path, self.requester(calls, failure_at=2))
            self.assertEqual(json.loads((path / "summary.json").read_text()), result)
            self.assertEqual(len(list(path.glob("*/result.json"))), 2)
        self.assertFalse(result["passed"])
        self.assertEqual(len(calls), 2)

    def test_repeat_token_mismatch_stops_at_four(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            result = CLIENT.run_session("http://localhost", "test", Path(tmp) / "run", self.requester(calls, change_repeat=True))
        self.assertFalse(result["passed"])
        self.assertEqual(len(calls), 4)

    def test_existing_evidence_is_not_overwritten(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(FileExistsError):
            CLIENT.run_session("http://localhost", "test", tmp, self.requester(calls))
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
