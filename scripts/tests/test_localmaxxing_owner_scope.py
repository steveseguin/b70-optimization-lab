"""The documented SPEED3 exception admits one result, never a blanket bypass."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import submit_localmaxxing_results as submit


QUEUE = (Path(__file__).resolve().parents[2] /
    "experiments/qwen38-flash-next-ud-iq3xxs-b70/data/"
    "20261015-own-rt-iq3-tp2-c4096-s24dr0-localmaxxing-payload-queue.json")


class OwnerScopeTest(unittest.TestCase):
    def setUp(self):
        self.item = json.loads(QUEUE.read_text())[0]
        self.flags = self.item["payload"]["engineFlags"]

    def test_authorized_result_passes_with_strict_gate_still_false(self):
        self.assertIs(self.flags["realisticSuiteGatePassed"], False)
        self.assertIs(self.flags["rawRealisticFinalGate"]["passed"], False)
        self.assertEqual(submit.preflight_payload(self.item), [])

    def test_no_authorization_refused_even_if_marker_is_flipped(self):
        del self.flags["realisticSuiteScopeException"]
        for marker in (False, True):
            with self.subTest(marker=marker):
                self.flags["realisticSuiteGatePassed"] = marker
                self.assertTrue(any("owner authorization" in e for e in
                                    submit.preflight_payload(self.item)))

    def test_exception_cannot_change_scope_identity_or_raw_gate(self):
        changes = {
            "realisticSuiteScopeException": {}, "requestedMaxNew": 512,
            "realisticOutputTokenCounts": [128] * 11,
            "draftRank": 1, "targetSplit": [22, 26],
            "rawRealisticFinalGate": {"passed": True},
            "realisticSuiteGatePassed": True,
            "promotionAttestationSha256": "0" * 64,
            "promotionIdentity": {"runtime_revision": "other"},
            "promptSha256": ["0" * 64] * 12,
        }
        for key, value in changes.items():
            with self.subTest(key=key):
                item = copy.deepcopy(self.item)
                item["payload"]["engineFlags"][key] = value
                self.assertTrue(submit.preflight_payload(item))

    def test_higher_repeat_cannot_replace_registered_headline(self):
        self.item["payload"]["tokSOut"] = 38.21692500912173
        self.assertTrue(submit.preflight_payload(self.item))

    def test_other_safety_and_metric_checks_still_apply(self):
        for key, value in (("realisticSuiteCachedTokensAllZero", False),
                           ("metricWindowIntervals", 100),
                           ("diagnostic_unsealed", True), ("qualifying", False),
                           ("historyAccelerated", True)):
            with self.subTest(key=key):
                item = copy.deepcopy(self.item)
                item["payload"]["engineFlags"][key] = value
                self.assertTrue(submit.preflight_payload(item))

    def test_wire_projection_discloses_exception_and_false_strict_gate(self):
        extra = submit.api_engine_flags(self.flags)["extraFlags"]
        self.assertIn(submit.OWNER_128_RULE, extra)
        self.assertIn('"strict512GatePassed": false', extra)
        self.assertIn(submit.OWNER_128_AUTHORIZATION["authorization_text"],
                      self.item["payload"]["notes"])

    def test_malformed_authorization_is_refused(self):
        self.flags["realisticSuiteScopeException"] = "yes"
        self.assertTrue(submit.preflight_payload(self.item))

    def check_changed_attestation_refused(self, change):
        path = submit.REPO_ROOT / self.flags["promotionAttestation"]
        att = json.loads(path.read_bytes())
        change(att)
        raw = json.dumps(att).encode()
        self.flags["promotionAttestationSha256"] = hashlib.sha256(raw).hexdigest()
        read_bytes = Path.read_bytes
        with patch.object(Path, "read_bytes", lambda p: raw if p == path else read_bytes(p)):
            self.assertTrue(submit.preflight_payload(self.item))

    def test_authorization_must_also_exist_in_bound_evidence(self):
        self.check_changed_attestation_refused(
            lambda att: att["submission_scope"].pop("owner_authorization"))

    def test_unqualified_bound_evidence_is_refused(self):
        self.check_changed_attestation_refused(lambda att: att.update(qualifying=False))


if __name__ == "__main__":
    unittest.main()
