"""CPU-only evidence rejection tests; no server or model is loaded."""
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("extract_prefill", Path(__file__).with_name("extract-fp8-one-launch-prefill.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files, cls.manifest = module.load_evidence()

    def mutate_json(self, name, update):
        files = dict(self.files)
        data = json.loads(files[name])
        update(data)
        files[name] = json.dumps(data).encode()
        return files

    def test_complete_receipts(self):
        result = module.extract(self.files, self.manifest)
        self.assertEqual(len(result["rows"]), 6)
        self.assertEqual(result["prefill_aggregate"]["median_tok_s"], 2164.0807055481273)
        self.assertFalse(result["headline_eligible"])

    def test_changed_prompt_rejected(self):
        files = self.mutate_json("run/screen/measure-prose-512-0-request.json", lambda d: d["prompt"].pop())
        with self.assertRaises(AssertionError):
            module.extract(files, self.manifest)

    def test_forged_decode_rate_rejected(self):
        files = self.mutate_json("run/screen/summary.json", lambda d: d["rows"][0].update(decode_token_1_to_100_tps=999))
        with self.assertRaises(AssertionError):
            module.extract(files, self.manifest)

    def test_nonzero_cache_rejected(self):
        files = dict(self.files)
        path = "run/screen/measure-prose-512-0-sse.jsonl"
        events = [json.loads(line) for line in files[path].splitlines()]
        for event in events:
            if event["data"] == "[DONE]":
                continue
            data = json.loads(event["data"])
            if data.get("usage"):
                data["usage"]["prompt_tokens_details"]["cached_tokens"] = 1
                event["data"] = json.dumps(data)
        files[path] = ("\n".join(json.dumps(x) for x in events) + "\n").encode()
        with self.assertRaises(AssertionError):
            module.extract(files, self.manifest)

    def test_repeated_output_divergence_rejected(self):
        files = dict(self.files)
        path = "run/screen/measure-prose-512-1-sse.jsonl"
        events = [json.loads(line) for line in files[path].splitlines()]
        for event in events:
            if event["data"] == "[DONE]":
                continue
            data = json.loads(event["data"])
            choices = data.get("choices", [])
            if choices and choices[0].get("token_ids"):
                choices[0]["token_ids"][0] += 1
                event["data"] = json.dumps(data)
                break
        files[path] = ("\n".join(json.dumps(x) for x in events) + "\n").encode()
        summary = json.loads(files["run/screen/summary.json"])
        next(row for row in summary["rows"] if row["key"] == "prose-512" and row["repeat"] == 1)["token_ids"][0] += 1
        files["run/screen/summary.json"] = json.dumps(summary).encode()
        with self.assertRaises(AssertionError):
            module.extract(files, self.manifest)

    def test_fault_after_stop_rejected(self):
        files = dict(self.files)
        files["run/after-kernel.log"] += b"\nxe 0000:23:00.0: GPU reset\n"
        with self.assertRaises(AssertionError):
            module.extract(files, self.manifest)


if __name__ == "__main__":
    unittest.main()
