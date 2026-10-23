"""Regression from the retained first run: census exists only after shutdown."""
import copy
import importlib.util
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

P = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("p207_harness_regression", P / "host_probe.py")
H = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(H)


class CensusTiming(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="p207-census-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.request = self.directory / "owner/requests/fresh-a"
        self.request.mkdir(parents=True)
        with tarfile.open(P / "lineage/before-final-census-join/raw-failed-host-proof.tar.gz", "r:gz") as archive:
            self.census = archive.extractfile("chunk/owner/census.json").read()
            for name in ("paired-sites.jsonl", "prefill-chunks.jsonl"):
                (self.request / name).write_bytes(archive.extractfile("chunk/owner/requests/fresh-a/" + name).read())
        self.trace = {"chunks": H.jsonl(self.request / "prefill-chunks.jsonl")}

    def test_request_trace_valid_without_future_census(self):
        self.assertFalse((self.directory / "owner/census.json").exists())
        records = H.paired_sites(self.directory, "fresh-a", self.trace, True)
        self.assertEqual(len(records), 8)
        with self.assertRaises(FileNotFoundError):
            H.validate_paired_census(self.directory, records)
        (self.directory / "owner/census.json").write_bytes(self.census)
        H.validate_paired_census(self.directory, records)

    def test_request_time_missing_issue_and_alias_still_refuse(self):
        records = H.jsonl(self.request / "paired-sites.jsonl")
        wrong = copy.deepcopy(records)
        wrong[0]["issued"] = False
        for changed in (wrong, records[:-1]):
            (self.request / "paired-sites.jsonl").write_text("\n".join(map(json.dumps, changed)))
            with self.assertRaises(RuntimeError):
                H.paired_sites(self.directory, "fresh-a", self.trace, True)
        wrong = copy.deepcopy(records)
        wrong[0]["input_ids"][1] = wrong[0]["input_ids"][0]
        (self.request / "paired-sites.jsonl").write_text("\n".join(map(json.dumps, wrong)))
        with self.assertRaisesRegex(RuntimeError, "aliases"):
            H.paired_sites(self.directory, "fresh-a", self.trace, True)

    def test_final_census_join_still_refuses_wrong_bound_allocation(self):
        records = H.paired_sites(self.directory, "fresh-a", self.trace, True)
        (self.directory / "owner/census.json").write_bytes(self.census)
        records[0]["weight_id"] += 1
        with self.assertRaisesRegex(RuntimeError, "captured IDs"):
            H.validate_paired_census(self.directory, records)


if __name__ == "__main__":
    unittest.main()
