"""Read-only replay of retained P211 bytes; never starts native or device work."""
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
                if member.name in cls.raw or member.size > 16 * 1024**2:
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
        self.assertEqual(plan["total_owner_processes"], 4)
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
        for name, expected in authority["source_sha256"].items():
            self.assertEqual(digest((ROOT / name).read_bytes()), expected, name)

    def test_complete_checkpoint_bytes_and_historical_oracles(self):
        binary = self.proof["plan"]["binary_sha256"]
        expected_ids = set(self.proof["direct"]["checkpoints"])
        self.assertEqual(len(expected_ids), 13)
        self.assertEqual(expected_ids, set(self.proof["paired"]["checkpoints"]))
        for checkpoint in expected_ids:
            for variant in ("direct", "serial", "paired"):
                prefix = f"{variant}/checkpoints/{checkpoint}/"
                manifest = self.obj(prefix + "manifest.json")
                self.assertEqual(manifest["label"], "experimental-host-engine-cache")
                self.assertEqual(manifest["contract"], "v1.2+p211")
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
                    self.assertEqual(data, self.raw[f"direct/checkpoints/{checkpoint}/{name}"])
                    if checkpoint in expected_ids:
                        old = Path(self.proof["plan"]["p207_reference"]["directory"]) / "serial/checkpoints" / checkpoint / name
                        self.assertEqual(data, old.read_bytes())

    def test_all_raw_prefill_endpoints_and_chunk_counters(self):
        for variant in ("serial", "paired"):
            count = chunks = tails = 0
            for request, row in self.rows(variant).items():
                suffix = f"owner/requests/{request}/"
                baseline = {x["published_position"]: x for x in self.lines("direct/" + suffix + "serial-prefill-state.jsonl")}
                pairs = self.lines(variant + "/" + suffix + "prefill-chunks.jsonl")
                single = self.lines(variant + "/" + suffix + "serial-prefill-state.jsonl")
                self.assertEqual(pairs, row["trace"]["chunks"])
                self.assertEqual(single, row["trace"]["serial_endpoints"])
                result = self.obj(variant + "/" + suffix + "result.json")
                self.assertEqual(result["p211_host_chunk2"], variant == "paired")
                self.assertEqual(result["p211_cache_mode"], variant)
                self.assertEqual(result["p211_chunk_count"], len(pairs))
                for item in pairs + single:
                    self.assertEqual(len(item["canonical_state_sha256"]), 20)
                    self.assertEqual(item["canonical_state_sha256"], baseline[item["published_position"]]["canonical_state_sha256"])
                    self.assertLess(item["published_position"], len(row["input"]))
                    count += 1
                for item in pairs:
                    self.assertEqual(item["count"], 2)
                    self.assertEqual(item["start"] // 32, (item["start"] + 1) // 32)
                chunks += len(pairs)
                tails += len(single)
            self.assertEqual((count, chunks, tails), (108, 100, 8))

    def test_decode_inputs_and_pending_boundary(self):
        for request, row in self.rows("paired").items():
            suffix = f"owner/requests/{request}/"
            stable = lambda x: {k: x[k] for k in ("token_index", "generated_index", "input_token", "token_id")}
            records = []
            for variant in ("direct", "serial", "paired"):
                native = self.obj(variant + "/" + suffix + "result.json")
                self.assertEqual(native["tokens"], row["tokens"])
                self.assertEqual(native["cached_tokens"], row["start_position"])
                records.append([stable(x) for x in self.lines(variant + "/" + suffix + "timings.jsonl") if x["kind"] == "generated_token"])
            self.assertEqual(records[0], records[1])
            self.assertEqual(records[0], records[2])
            self.assertEqual(len(records[0]), len(row["tokens"]))
            if not row["same_generation"]:
                self.assertEqual(records[0][0]["input_token"], row["input"][-1])
                self.assertEqual(records[0][0]["token_index"], len(row["input"]) - 1)
        for variant in ("direct", "serial", "paired"):
            seed = self.obj(f"{variant}/checkpoints/boundary-seed/manifest.json")["token_state"]
            self.assertEqual(seed["position"], 31)
            row = self.rows(variant)["boundary-append"]
            self.assertEqual(row["start_position"], 31)
            self.assertEqual(row["input"][31], seed["next_token"])
            self.assertEqual(self.raw[f"{variant}/checkpoints/boundary-append/tokens.bin"], self.raw[f"{variant}/checkpoints/boundary-fresh/tokens.bin"])
            if variant == "paired":
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
        for variant in ("direct", "serial", "paired"):
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
            self.assertIn(b"p211 cache2 requires HOST_ONLY mini pipeline resident single-owner mode", self.raw[prefix + "stderr.log"])
            for name in ("stderr", "stdout"):
                self.assertEqual(digest(self.raw[prefix + name + ".log"]), row[name + "_sha256"])

    def test_actual_paired_sites_and_retained_bindings(self):
        census = self.obj("paired/owner/census.json")[0]["allocations"]
        by_id = {row["id"]: row for row in census}
        issued = skipped = 0
        for request, row in self.rows("paired").items():
            records = self.lines(f"paired/owner/requests/{request}/paired-sites.jsonl")
            self.assertEqual(records, row["paired_sites"])
            self.assertEqual([(x["start"], x["layer"], x["op"]) for x in records],
                             [(x["start"], layer, op) for x in row["trace"]["chunks"]
                              for layer in (0, 2) for op in ("qkv", "z")])
            self.assertEqual(self.lines(f"direct/owner/requests/{request}/paired-sites.jsonl"), [])
            self.assertEqual(self.lines(f"serial/owner/requests/{request}/paired-sites.jsonl"), [])
            for record in records:
                self.assertTrue(record["captured"] and record["issued"])
                self.assertEqual(record["skipped_original_sites"], 2)
                ids = record["input_ids"] + record["output_ids"] + record["inject_ids"] + record["workspace_ids"] + [record["weight_id"]]
                self.assertEqual(len(ids), len(set(ids)))
                for r in range(2):
                    self.assertEqual(by_id[record["input_ids"][r]]["label"], f"card0:p211:row{r}:retained0")
                    self.assertEqual(by_id[record["inject_ids"][r]]["label"], f"card0:p211:row{r}:retained1")
                    output = 2 if record["op"] == "qkv" else 3
                    self.assertEqual(by_id[record["output_ids"][r]]["label"], f"card0:p211:row{r}:retained{output}")
                weight = "attn_qkv" if record["op"] == "qkv" else "attn_gate"
                self.assertEqual(by_id[record["weight_id"]]["label"], f"card0:weight:blk.{record['layer']}.{weight}.weight")
                issued += 1
                skipped += record["skipped_original_sites"]
        self.assertEqual((issued, skipped), (400, 800))

    def test_indirect_adapter_actual_bytes_and_fault_owners(self):
        result = self.proof["indirect_arithmetic"]
        self.assertTrue(result["passed"])
        self.assertEqual(result["returncode"], 0)
        proof = self.obj("indirect-proof/indirect-proof.json")
        self.assertEqual(proof, result["proof"])
        self.assertEqual(digest(self.raw["indirect-proof/indirect-proof.json"]), result["proof_sha256"])
        self.assertEqual(len(proof["checks"]), 27)
        self.assertTrue(all(value is True for value in proof["checks"].values()))
        self.assertEqual([x["name"] for x in proof["cases"]],
                         ["gate_up_valid", "gate_up_invalid", "down_valid", "down_invalid"])
        for case in proof["cases"]:
            self.assertEqual(case["count"], 10)
            for output in case["outputs"]:
                data = bytes.fromhex(output["output_hex"])
                self.assertEqual(len(data), 80)
                self.assertEqual(digest(data), output["contiguous_sha256"])
                self.assertEqual(digest(data), output["indirect_sha256"])
                status = bytes.fromhex(output["status_hex"])
                invalid = int(case["name"].endswith("_invalid"))
                self.assertEqual(struct.unpack("<10I", status), (0, invalid, invalid, 0, 0, 0, 0, 0, 0, 0))
                self.assertEqual(digest(status), output["status_sha256"])
        self.assertEqual(len(proof["owner_receipts"]), 9)
        for name, owner in proof["owner_receipts"].items():
            fault = name in ("outside_first", "misaligned_first", "zero_generation_first", "outside_later")
            self.assertTrue(owner["safe_to_exit"])
            self.assertEqual((owner["in_flight"], owner["live_bytes"], owner["exit_code"]), (0, 0, int(fault)))
            if fault:
                self.assertEqual(owner["status"], "failed-drained")
                self.assertEqual(proof["errors"][name], "p211 indirect payload outside retained owned span")

    def test_cache_route_bytes_frozen_policy_reset_and_evictions(self):
        all_modes = {}
        for variant in ("serial", "paired"):
            records = []; previous = set(); previous_hash = None
            for request, row in self.rows(variant).items():
                prefix = f"{variant}/owner/requests/{request}/"
                reset = self.obj(prefix + "cache-reset.json")
                self.assertTrue(reset["preserved"] and reset["passed"])
                self.assertEqual(reset["capacity"], 4096)
                if previous_hash is not None:
                    self.assertEqual(reset["normalized_table_sha256"], previous_hash)
                rows = self.lines(prefix + "cache-intervals.jsonl")
                self.assertEqual(rows, row["cache"]["intervals"])
                for item in rows:
                    raw = b"".join(struct.pack("<III", *x) for x in item["route_triples"])
                    self.assertEqual(digest(raw), item["route_sha256"])
                    self.assertEqual(len(item["routes"]), item["count"] * 40)
                    for index, (expert, triple) in enumerate(zip(item["routes"], item["route_triples"], strict=True)):
                        self.assertEqual(expert, ((index // 10) % 4) * 16 + triple[0])
                    self.assertEqual(item["hits"], sum(x in previous for x in item["routes"]))
                    self.assertEqual(item["hits"] + item["misses"], len(item["routes"]))
                    self.assertTrue(item["frozen_table_payload"])
                    previous = set(item["resident_ids"])
                    previous_hash = item["normalized_table_sha256"]
                    records.append(item)
            self.assertEqual(len(records), 181)
            self.assertEqual(sum(x["count"] for x in records), 281)
            self.assertEqual([x["epoch"] for x in records], list(range(1, 182)))
            self.assertEqual([x["publications_total"] for x in records], list(range(2, 183)))
            self.assertGreater(sum(x["evictions"] for x in records), 0)
            self.assertGreater(sum(x["hits"] for x in records), 0)
            all_modes[variant] = records
        self.assertEqual(all_modes["serial"], all_modes["paired"])

    def test_failed_cached_chunk_never_publishes_or_accepts_retry(self):
        result = self.proof["intentional_partial_failure"]
        self.assertTrue(result["passed"])
        self.assertEqual(result["returncode"], 1)
        self.assertFalse(result["incident_sigterm_sent"] or result["retained_owner"])
        self.assertIn("p211 intentional partial chunk refusal", result["original_error"])
        prefix = "intentional-partial-failure/"
        cache = self.obj(prefix + "owner/cache-failure.json")
        self.assertEqual(cache, result["cache_failure"])
        self.assertTrue(cache["cache_active"] and cache["poisoned"])
        self.assertFalse(cache["updating"] or cache["rollback_claimed"])
        self.assertEqual((cache["start"], cache["count"]), (0, 2))
        self.assertTrue(result["poisoned_intake_refusal"])
        self.assertNotIn(prefix + "owner/requests/fault/result.json", self.raw)
        self.assertFalse(any(name.startswith(prefix + "checkpoints/") and name.endswith("manifest.json") for name in self.raw))
        self.assertEqual(self.lines(prefix + "owner/requests/fault/cache-intervals.jsonl"), [])
        self.assertEqual(self.lines(prefix + "owner/requests/fault/prefill-chunks.jsonl"), [])
        owner = self.obj(prefix + "owner/receipt.json")
        self.assertFalse(owner["passed"])
        self.assertTrue(owner["safe_to_exit"])


if __name__ == "__main__":
    unittest.main()
