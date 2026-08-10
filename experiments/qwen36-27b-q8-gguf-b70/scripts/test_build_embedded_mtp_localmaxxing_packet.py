#!/usr/bin/env python3
"""Policy tests for the reviewed embedded-MTP LocalMaxxing builder."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("build-embedded-mtp-localmaxxing-packet.py")
SPEC = importlib.util.spec_from_file_location("embedded_mtp_lmx_builder", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


class NaturalEosSubmissionPolicyTests(unittest.TestCase):
    def test_natural_eos_after_primary_window_is_eligible(self) -> None:
        policy = BUILDER.completion_length_policy([512] * 11 + [248])
        self.assertTrue(policy["eligible"])
        self.assertEqual(policy["minimumObservedGeneratedTokens"], 248)
        self.assertFalse(policy["allRowsReachedRequestMaximum"])
        self.assertTrue(policy["naturalStopsAfterPrimaryWindowAllowed"])

    def test_natural_eos_before_primary_window_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "100-event primary window"):
            BUILDER.completion_length_policy([512] * 11 + [99])

    def test_request_cap_is_not_an_all_rows_requirement(self) -> None:
        policy = BUILDER.completion_length_policy([100, 248, 511, 512])
        self.assertTrue(policy["eligible"])
        self.assertFalse(policy["allRowsReachedRequestMaximum"])


if __name__ == "__main__":
    unittest.main()
