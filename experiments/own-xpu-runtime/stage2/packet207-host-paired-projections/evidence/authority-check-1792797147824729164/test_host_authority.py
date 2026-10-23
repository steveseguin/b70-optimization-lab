"""Read-only replay of retained P207 bytes; never starts native or device work."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import struct
import tarfile
import unittest

P = Path(__file__).resolve().parents[1]
ROOT = P.parents[3]


def digest(data):
    return hashlib.sha256(data).hexdigest()


class RetainedAuthority(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proof = json.loads((P / "evidence/host-proof.json").read_text())
        cls.index = json.loads((P / "evidence/raw-host-proof-index.json").read_text())
        cls.archive = P / cls.index["archive"]
        cls.raw = {}
        with tarfile.open(cls.archive, "r:gz") as stream:
            for member in stream:
                name = PurePosixPath(member.name)
                if not member.isfile() or name.is_absolute() or ".." in name.parts:
                    raise AssertionError("archive contains nonregular or unsafe member")
                if member.name in cls.raw or member.size > 2 * 1024**2:
                    raise AssertionError("duplicate or unexpectedly large member")
                cls.raw[member.name] = stream.extractfile(member).read()

    def obj(self, name):
        return json.loads(self.raw[name])

    def lines(self, name):
        return [json.loads(line) for line in self.raw.get(name, b"").splitlines()]

    def rows(self, variant):
        return {row["id"]: row for row in self.proof[variant]["rows"]}

    def test_archive_inventory_exact_bytes(self):
        self.assertEqual(digest(self.archive.read_bytes()), self.index["archive_sha256"])
        self.assertEqual(set(self.raw), set(self.index["files"]))
        self.assertEqual(len(self.raw), self.index["file_count"])
        self.assertEqual(sum(map(len, self.raw.values())), self.index["logical_bytes"])
        for name, data in self.raw.items():
            with self.subTest(name=name):
                self.assertEqual(self.index["files"][name], {"bytes": len(data), "sha256": digest(data)})
        self.assertEqual(self.obj("result.json"), self.proof)

    def test_executed_source_and_binary_identity(self):
        plan = self.obj("plan.json")
        self.assertEqual(plan, self.proof["plan"])
        self.assertEqual(plan["total_owner_processes"], 2)
        self.assertEqual(plan["standalone_abi_processes"], 1)
        for name, expected in plan["source_sha256"].items():
            self.assertEqual(digest((ROOT / name).read_bytes()), expected, name)
        build = P / "evidence/build-compile-only.json"
        self.assertEqual(digest(build.read_bytes()), plan["build_receipt_sha256"])
        host = next(x for x in json.loads(build.read_text())["plans"] if x["target"] == "host")
        self.assertEqual(host["binary_sha256"], plan["binary_sha256"])
        self.assertEqual(digest(Path(plan["binary"]).read_bytes()), plan["binary_sha256"])
        for name, expected in host["repository_dependencies"].items():
            self.assertEqual(digest((ROOT / name).read_bytes()), expected, name)
        for name, expected in host["objects"].items():
            self.assertEqual(digest(Path(name).read_bytes()), expected, name)
        authority = json.loads((P / "authority-inputs.json").read_text())
        for name, expected in authority["artifacts_sha256"].items():
            self.assertEqual(digest((ROOT / name).read_bytes()), expected, name)

    def test_complete_checkpoint_bytes_and_historical_oracles(self):
        binary = self.proof["plan"]["binary_sha256"]
        expected_ids = set(self.proof["serial"]["checkpoints"])
        self.assertEqual(len(expected_ids), 13)
        self.assertEqual(expected_ids, set(self.proof["chunk"]["checkpoints"]))
        for checkpoint in expected_ids:
            for variant in ("serial", "chunk"):
                prefix = f"{variant}/checkpoints/{checkpoint}/"
                manifest = self.obj(prefix + "manifest.json")
                self.assertEqual(manifest["label"], "experimental-host-paired-projections")
                self.assertEqual(manifest["contract"], "v1.2+p207")
                self.assertEqual(manifest["engine"]["binary_sha256"], binary)
                self.assertEqual(manifest["qualified_by"]["device_gates"], [])
                self.assertEqual(len(manifest["blobs"]), 20)
                for blob in manifest["blobs"]:
                    data = self.raw[prefix + blob["name"] + ".bin"]
                    self.assertEqual(len(data), blob["bytes"])
                    self.assertEqual(digest(data), blob["sha256"])
                for name, expected in self.proof[variant]["checkpoints"][checkpoint]["files_sha256"].items():
                    data = self.raw[prefix + name]
                    self.assertEqual(digest(data), expected)
                    self.assertEqual(data, self.raw[f"serial/checkpoints/{checkpoint}/{name}"])
                    if checkpoint in expected_ids:
                        old = Path(self.proof["plan"]["p206_reference"]["directory"]) / "serial/checkpoints" / checkpoint / name
                        self.assertEqual(data, old.read_bytes())

    def test_all_raw_prefill_endpoints_and_chunk_counters(self):
        count = chunks = tails = 0
        for request, row in self.rows("chunk").items():
            suffix = f"owner/requests/{request}/"
            baseline = {x["published_position"]: x for x in self.lines("serial/" + suffix + "serial-prefill-state.jsonl")}
            paired = self.lines("chunk/" + suffix + "prefill-chunks.jsonl")
            single = self.lines("chunk/" + suffix + "serial-prefill-state.jsonl")
            self.assertEqual(paired, row["trace"]["chunks"])
            self.assertEqual(single, row["trace"]["serial_endpoints"])
            result = self.obj("chunk/" + suffix + "result.json")
            self.assertTrue(result["p207_host_chunk2"])
            self.assertEqual(result["p207_chunk_count"], len(paired))
            for item in paired + single:
                self.assertEqual(len(item["canonical_state_sha256"]), 20)
                self.assertEqual(item["canonical_state_sha256"], baseline[item["published_position"]]["canonical_state_sha256"])
                self.assertLess(item["published_position"], len(row["input"]))
                count += 1
            for item in paired:
                self.assertEqual(item["count"], 2)
                self.assertEqual(item["start"] // 32, (item["start"] + 1) // 32)
            chunks += len(paired)
            tails += len(single)
        self.assertEqual((count, chunks, tails), (108, 100, 8))

    def test_decode_inputs_and_pending_boundary(self):
        for request, row in self.rows("chunk").items():
            suffix = f"owner/requests/{request}/"
            stable = lambda x: {k: x[k] for k in ("token_index", "generated_index", "input_token", "token_id")}
            records = []
            for variant in ("serial", "chunk"):
                native = self.obj(variant + "/" + suffix + "result.json")
                self.assertEqual(native["tokens"], row["tokens"])
                self.assertEqual(native["cached_tokens"], row["start_position"])
                records.append([stable(x) for x in self.lines(variant + "/" + suffix + "timings.jsonl") if x["kind"] == "generated_token"])
            self.assertEqual(records[0], records[1])
            self.assertEqual(len(records[0]), len(row["tokens"]))
            if not row["same_generation"]:
                self.assertEqual(records[0][0]["input_token"], row["input"][-1])
                self.assertEqual(records[0][0]["token_index"], len(row["input"]) - 1)
        for variant in ("serial", "chunk"):
            seed = self.obj(f"{variant}/checkpoints/boundary-seed/manifest.json")["token_state"]
            self.assertEqual(seed["position"], 31)
            row = self.rows(variant)["boundary-append"]
            self.assertEqual(row["start_position"], 31)
            self.assertEqual(row["input"][31], seed["next_token"])
            self.assertEqual(self.raw[f"{variant}/checkpoints/boundary-append/tokens.bin"], self.raw[f"{variant}/checkpoints/boundary-fresh/tokens.bin"])
            if variant == "chunk":
                self.assertEqual(row["trace"]["single_prefill_positions"], [31, 36])
                self.assertEqual([x["start"] for x in row["trace"]["chunks"]], [32, 34])
            resumed = self.rows(variant)["resume-a"]
            self.assertEqual(resumed["trace"]["chunks"], [])
            self.assertEqual(resumed["trace"]["single_prefill_positions"], [])
            self.assertEqual(resumed["trace"]["generated_indices"], [2, 3, 4, 5])

    def test_safe_terminal_and_exact_postreply_dispositions(self):
        self.assertTrue(self.proof["passed"])
        self.assertFalse(self.proof["device_executed"])
        self.assertFalse(self.proof["model_executed"])
        for variant in ("serial", "chunk"):
            result = self.proof[variant]
            self.assertEqual(result["returncode"], 0)
            self.assertFalse(result["retained_owner"])
            self.assertFalse(result["incident_sigterm_sent"])
            self.assertEqual(result["stopped"]["completed_requests"], 16)
            self.assertEqual(result["stopped"]["completed_controls"], 16)
            self.assertFalse(result["stopped"]["discarded_pending"])
            self.assertEqual(result["stopped"]["pending_request_id"], "")
            controls = [row["control"] for row in result["rows"]]
            self.assertEqual(sum(x["event"] == "checkpoint-saved" for x in controls), 13)
            self.assertEqual(sum(x["event"] == "request-released" for x in controls), 3)
            for control in controls:
                self.assertTrue(control["request_disposed"])
                self.assertTrue(control["request_quiesced"])
            self.assertTrue(controls[-1]["final_request"])
            owner = self.obj(f"{variant}/owner/receipt.json")
            self.assertTrue(owner["passed"] and owner["safe_to_exit"])
            for teardown in owner["teardown"]:
                self.assertEqual((teardown["in_flight"], teardown["live_bytes"], teardown["exit_code"]), (0, 0, 0))
                self.assertTrue(teardown["safe_to_exit"])

    def test_early_refusal_logs_without_owner_creation(self):
        self.assertEqual(len(self.proof["parser_refusals"]), 10)
        for row in self.proof["parser_refusals"]:
            prefix = "parser-refusals/" + row["name"] + "/"
            self.assertEqual(row["returncode"], 1)
            self.assertFalse(row["owner_output_created"])
            self.assertFalse(row["incident_sigterm_sent"])
            self.assertFalse(any(name.startswith(prefix + "must-not-create-owner/") for name in self.raw))
            self.assertIn(b"p207 chunk2 requires HOST_ONLY mini pipeline resident single-owner mode", self.raw[prefix + "stderr.log"])
            for name in ("stderr", "stdout"):
                self.assertEqual(digest(self.raw[prefix + name + ".log"]), row[name + "_sha256"])

    def test_actual_paired_sites_and_retained_bindings(self):
        census = self.obj("chunk/owner/census.json")[0]["allocations"]
        by_id = {row["id"]: row for row in census}
        issued = skipped = 0
        for request, row in self.rows("chunk").items():
            records = self.lines(f"chunk/owner/requests/{request}/paired-sites.jsonl")
            self.assertEqual(records, row["paired_sites"])
            self.assertEqual([(x["start"], x["layer"], x["op"]) for x in records],
                             [(x["start"], layer, op) for x in row["trace"]["chunks"]
                              for layer in (0, 2) for op in ("qkv", "z")])
            self.assertEqual(self.lines(f"serial/owner/requests/{request}/paired-sites.jsonl"), [])
            for record in records:
                self.assertTrue(record["captured"] and record["issued"])
                self.assertEqual(record["skipped_original_sites"], 2)
                ids = record["input_ids"] + record["output_ids"] + record["inject_ids"] + record["workspace_ids"] + [record["weight_id"]]
                self.assertEqual(len(ids), len(set(ids)))
                for r in range(2):
                    self.assertEqual(by_id[record["input_ids"][r]]["label"], f"card0:p207:row{r}:retained0")
                    self.assertEqual(by_id[record["inject_ids"][r]]["label"], f"card0:p207:row{r}:retained1")
                    output = 2 if record["op"] == "qkv" else 3
                    self.assertEqual(by_id[record["output_ids"][r]]["label"], f"card0:p207:row{r}:retained{output}")
                weight = "attn_qkv" if record["op"] == "qkv" else "attn_gate"
                self.assertEqual(by_id[record["weight_id"]]["label"], f"card0:weight:blk.{record['layer']}.{weight}.weight")
                issued += 1
                skipped += record["skipped_original_sites"]
        self.assertEqual((issued, skipped), (400, 800))

    def test_separate_fullshape_q6_abi_reference_and_mutations(self):
        result = self.proof["paired_abi"]
        self.assertTrue(result["passed"])
        self.assertEqual(result["returncode"], 0)
        self.assertFalse(result["retained_owner"] or result["incident_sigterm_sent"])
        raw = self.raw["pair-proof/pair-proof.json"]
        self.assertEqual(digest(raw), result["proof_sha256"])
        proof = json.loads(raw)
        self.assertEqual(proof, result["proof"])
        self.assertTrue(proof["passed"])
        self.assertFalse(proof["model_executed"] or proof["device_executed"])
        self.assertEqual([row["rows"] for row in proof["cases"]], [10240, 6144])
        for row in proof["cases"]:
            self.assertEqual((row["columns"], row["variant"], row["stride"], row["captured_operations"]), (2560, 6, 3380, 1))
            self.assertNotEqual(row["outputs"][0]["sha256"], row["outputs"][1]["sha256"])
            for output in row["outputs"]:
                self.assertEqual(output["bytes"], row["rows"] * 2)
                self.assertTrue(output["p33_equal"])
            for name in ("changed_row_independent", "changed_weight_consumed", "caller_metadata_immutable", "alias_extent_layout_refusals_unchanged"):
                self.assertTrue(row[name], name)
        self.assertEqual(len(proof["teardown"]), 2)
        for teardown in proof["teardown"]:
            self.assertEqual((teardown["exit_code"], teardown["in_flight"], teardown["live_bytes"]), (0, 0, 0))
            self.assertTrue(teardown["safe_to_exit"])



if __name__ == "__main__":
    unittest.main()
