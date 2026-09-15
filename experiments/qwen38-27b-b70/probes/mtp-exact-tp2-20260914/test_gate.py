from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import analyze
import gate
import nan_analysis as NA


def nan(bits):
    return bits & 0x7c00 == 0x7c00 and bits & 0x03ff


class GateFixtureTests(unittest.TestCase):
    def test_existing_fixture_cases_unchanged(self):
        frozen = {
            "cancel": ([0x3555, 0x7bff, 0x0001, 0x0400], [0xb555, 0xfbff, 0x8001, 0x8400]),
            "signed_zero": ([0, 0x8000, 0, 0x8000], [0, 0, 0x8000, 0x8000]),
            "subnormal": ([1, 0x3ff, 0x8001, 0x83ff], [1, 1, 0x8001, 0x8001]),
            "overflow": ([0x7bff, 0xfbff, 0x7bff, 0x3555], [0x7bff, 0xfbff, 0x3c00, 0x3555]),
            "rounding": ([0x3c00, 0x3c01, 0x3c02, 0xbc01], [0x1000, 0x1000, 0x1000, 0x9000]),
            "nan_inf": ([0x7c00, 0xfc00, 0x7e01, 0xfe02], [0xfc00, 0x7c00, 0x3c00, 0x7e03]),
        }
        for kind, patterns in frozen.items():
            self.assertEqual(gate.PATTERNS[kind], patterns)
        self.assertEqual(gate.KINDS[:7], ("varied", "cancel", "signed_zero", "subnormal", "overflow", "rounding", "nan_inf"))
        self.assertEqual(gate.KINDS, analyze.KINDS)

    def test_nan_matrix_has_nans_in_both_positions_signs_forms_and_payloads(self):
        r0, r1 = gate.PATTERNS["nan_matrix"]
        pairs = list(zip(r0, r1))
        self.assertEqual(len(pairs), NA.PERIOD)
        both = [(a, b) for a, b in pairs if nan(a) and nan(b)]
        self.assertIn((0xfe02, 0x7e03), both)
        self.assertIn((0x7e03, 0xfe02), both)
        for position in (0, 1):
            other = 1 - position
            lone = [p for p in pairs if nan(p[position]) and not nan(p[other])]
            values = {p[position] for p in lone}
            for sign in (0, 0x8000):
                for quiet in (0, 0x0200):
                    self.assertTrue(any(v & 0x8000 == sign and v & 0x0200 == quiet for v in values), (position, sign, quiet))
            self.assertGreaterEqual(len({v & 0x01ff for v in values}), 4)
        self.assertTrue(any(a & 0x8000 != b & 0x8000 for a, b in both))

    def test_add_mode_is_required_and_restricted(self):
        base = ["--library", "x.so", "--out", "o"]
        with mock.patch("sys.stderr"):
            with self.assertRaises(SystemExit):
                gate.parser().parse_args(base)
            with self.assertRaises(SystemExit):
                gate.parser().parse_args(base + ["--add-mode", "m9"])
        self.assertEqual(gate.parser().parse_args(base + ["--add-mode", "m3"]).add_mode, "m3")


    def test_nan_rule_defaults_to_bit_exact_and_accepts_class(self):
        base = ["--library", "x.so", "--out", "o", "--add-mode", "m0"]
        self.assertEqual(gate.parser().parse_args(base).nan_rule, "bit-exact")
        self.assertEqual(gate.parser().parse_args(base + ["--nan-rule", "nan-class"]).nan_rule, "nan-class")
        with mock.patch("sys.stderr"), self.assertRaises(SystemExit):
            gate.parser().parse_args(base + ["--nan-rule", "loose"])

    def test_outputs_equal_rules(self):
        from array import array
        ref = array("H", [0x7e03, 0x3c00, 0x0000]).tobytes()
        nan_payload = array("H", [0xfe02, 0x3c00, 0x0000]).tobytes()
        finite = array("H", [0x7e03, 0x3c01, 0x0000]).tobytes()
        signed_zero = array("H", [0x7e03, 0x3c00, 0x8000]).tobytes()
        nan_vs_number = array("H", [0x3c00, 0x3c00, 0x0000]).tobytes()
        self.assertTrue(gate.outputs_equal(ref, ref, "bit-exact"))
        self.assertFalse(gate.outputs_equal(nan_payload, ref, "bit-exact"))
        self.assertTrue(gate.outputs_equal(nan_payload, ref, "nan-class"))
        for other in (finite, signed_zero, nan_vs_number):
            self.assertFalse(gate.outputs_equal(other, ref, "nan-class"))
        with self.assertRaises(ValueError):
            gate.outputs_equal(ref, ref, "loose")


class GateExitTests(unittest.TestCase):
    def args(self, d):
        return SimpleNamespace(out=str(d), add_mode="m1")

    def test_quality_rejection_writes_receipt_and_exits_2_without_hard_exit(self):
        hard_exit = mock.Mock()
        def rejected(_):
            raise gate.QualityRejected("rank0-rows1-nan_matrix-0: exact-bit quality gate rejected")
        with tempfile.TemporaryDirectory() as d, mock.patch.dict("os.environ", {"RANK": "0"}):
            (Path(d) / "control.sock").write_text("")
            self.assertEqual(gate.run(self.args(d), rejected, hard_exit), gate.QUALITY_EXIT)
            receipt = (Path(d) / "rank0-QUALITY-REJECTED.json").read_text()
            self.assertFalse((Path(d) / "control.sock").exists())
            self.assertFalse((Path(d) / "rank0-FAULT.txt").exists())
        hard_exit.assert_not_called()
        self.assertIn('"process_group_destroyed": true', receipt)
        self.assertIn('"os_exit": false', receipt)

    def test_unknown_fault_keeps_hard_exit(self):
        hard_exit = mock.Mock()
        def fault(_):
            raise RuntimeError("Level Zero result 1879048196")
        with tempfile.TemporaryDirectory() as d, mock.patch.dict("os.environ", {"RANK": "1"}):
            gate.run(self.args(d), fault, hard_exit)
            self.assertIn("Level Zero", (Path(d) / "rank1-FAULT.txt").read_text())
        hard_exit.assert_called_once_with(gate.FAULT_EXIT)

    def test_success_returns_zero(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(gate.run(self.args(d), lambda _: None, mock.Mock()), 0)


if __name__ == "__main__":
    unittest.main()
