"""Read retained synthetic CPU results; never launch a model or rerun the probe."""
import hashlib
import json
from pathlib import Path
import unittest

P = Path(__file__).resolve().parents[1]
ROOT = P.parents[3]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def segment(text, start, end):
    i = text.index(start)
    return text[i:text.index(end, i)]


class AuthorityTests(unittest.TestCase):
    def test_source_and_inherited_object_pins(self):
        authority = read(P / "authority-inputs.json")
        for field in ("artifacts_sha256", "reused_host_object_sha256"):
            for name, expected in authority[field].items():
                with self.subTest(name=name):
                    self.assertEqual(sha(ROOT / name), expected)
        self.assertEqual(sha(P / "SOURCE-AUTHORITY.md"), authority["source_note_sha256"])

    def test_extracted_host_backend_is_exact(self):
        main = (P.parent / "packet198-postreply-checkpoint/build/native/main.cpp").read_text()
        start = main.index("class Host final : public packet18::LifetimeMock")
        body = main[start:main.index("\n};\n#endif", start) + 3]
        self.assertEqual(hashlib.sha256(body.encode()).hexdigest(),
                         read(P / "authority-inputs.json")["p198_host_backend_class_sha256"])
        candidate = (P / "host_backend.hpp").read_text()
        at = candidate.index("class Host final : public packet18::LifetimeMock")
        self.assertEqual(candidate[at:at + len(body)], body)

    def test_raw_checked_cpu_adapter_bodies_match(self):
        base = P.parent / "packet58j-onecard-port"
        raw = (base / "adapter.cpp").read_text()
        checked = (base / "build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/adapter.cpp").read_text()
        expected = read(P / "authority-inputs.json")["raw_checked_host_source_body_equality"]
        for name, first, last in (("simple_cpu", "template<class Team> void simple(", "bool simple_v2("),
                                  ("host_operations", "struct NgHost final:HostOperation", "#else")):
            with self.subTest(name=name):
                a, b = segment(raw, first, last), segment(checked, first, last)
                self.assertEqual(a, b)
                self.assertEqual(hashlib.sha256(a.encode()).hexdigest(), expected[name]["sha256"])

    def test_owner_source_and_object_share_historical_lineage(self):
        lineage = P.parent / "packet181-session-swap-v3/one-card/lineage"
        receipt = read(lineage / "build-receipt.json")["sources"]
        prefix = "experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/"
        self.assertEqual(sha(lineage / "native/generated/owner.cpp"),
                         receipt[prefix + "native/generated/owner.cpp"])
        authority = read(P / "authority-inputs.json")
        owner = [(n, h) for n, h in authority["reused_host_object_sha256"].items() if n.endswith("/owner.o")]
        self.assertEqual(len(owner), 1)
        self.assertEqual(owner[0][1], receipt[prefix + "build/gnu-host/owner.o"])


class RetainedCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = read(P / "evidence/host-capture.json")
        cls.build = read(P / "evidence/build.json")

    def require_checks(self, *names):
        for name in names:
            with self.subTest(name=name):
                self.assertIs(self.result["checks"][name], True)

    def test_compiler_dependency_binary_and_object_closure(self):
        self.assertIs(self.build["passed"], True)
        self.assertIs(self.result["passed"], True)
        self.assertEqual(self.result["build_receipt_sha256"], sha(P / "evidence/build.json"))
        self.assertEqual(self.result["source_sha256"], self.build["source_sha256"])
        self.assertEqual(sha(ROOT / self.build["binary"]), self.build["binary_sha256"])
        self.assertEqual(self.result["binary_sha256"], self.build["binary_sha256"])
        for name, expected in self.build["source_sha256"].items():
            with self.subTest(source=name):
                self.assertEqual(sha(ROOT / name), expected)
        parent = read(P.parent / "packet198-postreply-checkpoint/evidence/build-compile-only.json")
        inherited = next(x for x in parent["plans"] if x["target"] == "host")["objects"]
        for name, expected in self.build["reused_host_object_sha256"].items():
            with self.subTest(object=name):
                self.assertEqual(expected, inherited[name])
                self.assertEqual(sha(Path(name)), expected)

    def test_no_device_model_or_native_event_claim(self):
        self.assertIs(self.result["device_executed"], False)
        self.assertIs(self.result["model_executed"], False)
        self.assertIn("MockDevice", self.result["backend"])
        self.assertIn("simulated", self.result["completion_scope"])
        self.assertIn("simulated", self.build["completion_scope"])

    def test_real_capture_matches_eager_and_live_inputs_are_observed(self):
        self.require_checks("capture_does_not_execute", "captured_matches_eager_bytes",
                            "caller_metadata_mutation_does_not_rebind", "in_place_input_remains_live")
        h = self.result["byte_sha256"]
        self.assertEqual(h["eager"], h["captured"])
        self.assertNotEqual(h["changed_live_input"], h["captured"])

    def test_distinct_row_controls_and_shared_history(self):
        self.require_checks("fixed_row_position_pointers_distinct", "shared_history_bindings_retained",
                            "row0_position_capture", "state_and_rows_nonvacuous",
                            "shared_scratch_captured_consumer")

    def test_history_and_shared_payload_are_consumed_by_row1(self):
        self.require_checks("wrong_shared_history_differs", "wrong_row_payload_differs")
        h = self.result["byte_sha256"]
        for name in ("wrong_history_row1_streams", "wrong_payload_row1_streams",
                     "changed_live_input_row1_streams"):
            with self.subTest(negative=name):
                self.assertNotEqual(h[name], h["valid_row1_streams"])

    def test_publication_requires_complete_rows_and_owned_completion(self):
        self.require_checks("canonical_untouched_after_row0", "partial_rows_publication_refused",
                            "canonical_untouched_before_publication", "canonical_copy_exact",
                            "canonical_copy_after_completion", "pending_publication_refused",
                            "publication_copy_refusal_poisons", "publication_failure_is_partial_not_rollback",
                            "publication_refusal_owner_can_drain")

    def test_actual_arena_generation_and_pending_ownership(self):
        self.require_checks("allocate_preserves_generation", "unrelated_release_invalidates_captures",
                            "explicit_invalidation_refuses", "pending_release_refused", "pending_invalidate_refused")

    def test_guard_failure_refuses_partial_publication(self):
        self.require_checks("guard_refusal_before_row1", "partial_guard_refuses_publication",
                            "guard_refusal_owner_clean", "guard_refusal_sticky_no_retry")

    def test_backend_failure_retains_error_and_is_never_success(self):
        self.require_checks("backend_failure_original_error", "backend_failure_halts_owner",
                            "backend_failure_never_normal_success", "normal_teardown_success")
        self.assertEqual(self.result["backend_failure_status"], "failed-drained")

    def test_owner_teardown_receipts_preserve_failure_distinction(self):
        receipts = self.result["owner_receipts"]
        self.assertEqual(set(receipts), {"normal", "guard_refusal", "backend_failure", "publication_refusal"})
        for name, receipt in receipts.items():
            with self.subTest(owner=name):
                self.assertEqual(receipt["backend"], "MockDevice")
                self.assertTrue(receipt["safe_to_exit"])
                self.assertTrue(receipt["idle_marker_complete"])
                self.assertEqual(receipt["in_flight"], 0)
                self.assertEqual(receipt["live_bytes"], 0)
                self.assertEqual(receipt["sequence"][-4:],
                                 ["idle-marker-complete", "events-released", "queue-released", "context-released"])
                if name == "backend_failure":
                    self.assertEqual(receipt["status"], "failed-drained")
                    self.assertEqual(receipt["exit_code"], 1)
                    self.assertEqual(receipt["error"], "intentional host operation failure")
                else:
                    self.assertEqual(receipt["status"], "complete")
                    self.assertEqual(receipt["exit_code"], 0)
                    self.assertEqual(receipt["error"], "")


if __name__ == "__main__":
    unittest.main()
