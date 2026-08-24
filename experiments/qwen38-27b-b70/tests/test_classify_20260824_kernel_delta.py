#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "classify-20260824-kernel-delta.py"
)
REJECT_PATTERN = (
    r"Timedout job:|Kernel-submitted job timed out|VM job timed out|"
    r"device coredump|GT.*reset|reset (queued|started|done)|TLB.*timeout|"
    r"GuC.*(fail|error|timeout)|CT.*(fail|error|timeout)|"
    r"xe.*(device.?lost|fault|reset|hung|hang[: ]|tim(e|ed)[ -]?out|error)|"
    r"AER:.*(error|fatal|nonfatal)|Hardware Error|aer_status|aer_layer|RxErr|"
    r"NonFatalErr|nvme.*(timeout|reset|I/O error)|EXT4-fs error|segfault|"
    r"WARNING:|BUG:|Oops:"
)
PREFIX = "2026-08-24T11:47:45-04:00 steve-b70s kernel: "
KNOWN_MESSAGES = [
    "{3}[Hardware Error]: Hardware error from APEI Generic Hardware Error Source: 514",
    "{3}[Hardware Error]: It has been corrected by h/w and requires no further action",
    "{3}[Hardware Error]: event severity: corrected",
    "{3}[Hardware Error]:  Error 0, type: corrected",
    "{3}[Hardware Error]:   section_type: PCIe error",
    "{3}[Hardware Error]:   port_type: 0, PCIe end point",
    "{3}[Hardware Error]:   version: 0.2",
    "{3}[Hardware Error]:   command: 0x0406, status: 0x0010",
    "{3}[Hardware Error]:   device_id: 0000:01:00.0",
    "{3}[Hardware Error]:   slot: 0",
    "{3}[Hardware Error]:   secondary_bus: 0x00",
    "{3}[Hardware Error]:   vendor_id: 0x144d, device_id: 0xa80a",
    "{3}[Hardware Error]:   class_code: 010802",
    "{3}[Hardware Error]:   bridge: secondary_status: 0x0000, control: 0x0000",
    "{3}[Hardware Error]:   aer_cor_status: 0x00000001, aer_cor_mask: 0x00000000",
    "{3}[Hardware Error]:   aer_uncor_status: 0x00000000, aer_uncor_mask: 0x00100000",
    "{3}[Hardware Error]:   aer_uncor_severity: 0x004f6030",
    "{3}[Hardware Error]:   TLP Header: 00000000 00000000 00000000 00000000",
    "nvme 0000:01:00.0: aer_status: 0x00000001, aer_mask: 0x00000000",
    "nvme 0000:01:00.0:    [ 0] RxErr                  (First)",
    "nvme 0000:01:00.0: aer_layer=Physical Layer, aer_agent=Receiver ID",
]


def block(messages: list[str] | None = None) -> str:
    return "".join(f"{PREFIX}{message}\n" for message in (messages or KNOWN_MESSAGES))


class ClassifierTest(unittest.TestCase):
    def classify(self, delta: str) -> tuple[subprocess.CompletedProcess[str], dict, str, str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            delta_path = root / "delta.log"
            reject_path = root / "reject.log"
            accepted_path = root / "accepted.log"
            summary_path = root / "summary.json"
            delta_path.write_text(delta, encoding="utf-8")
            result = subprocess.run(
                [
                    str(SCRIPT),
                    "--delta",
                    str(delta_path),
                    "--reject-pattern",
                    REJECT_PATTERN,
                    "--reject-output",
                    str(reject_path),
                    "--accepted-output",
                    str(accepted_path),
                    "--summary-output",
                    str(summary_path),
                    "--max-known-nvme-events",
                    "1",
                ],
                check=False,
                text=True,
                capture_output=True,
            )
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            return (
                result,
                summary,
                reject_path.read_text(encoding="utf-8"),
                accepted_path.read_text(encoding="utf-8"),
            )

    def test_exact_known_block_is_preserved_and_accepted(self) -> None:
        result, summary, rejected, accepted = self.classify(block())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(summary["decision"], "pass")
        self.assertEqual(summary["known_nvme_accepted_count"], 1)
        self.assertEqual(summary["accepted_line_count"], 21)
        self.assertEqual(rejected, "")
        self.assertEqual(accepted, block())

    def test_empty_and_ordinary_kernel_lines_pass(self) -> None:
        ordinary = f"{PREFIX}docker0: port 1 entered forwarding state\n"
        result, summary, rejected, accepted = self.classify(ordinary)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(summary["known_nvme_accepted_count"], 0)
        self.assertEqual(rejected, "")
        self.assertEqual(accepted, "")

    def assert_mutation_rejected(self, old: str, new: str) -> None:
        mutated = [message.replace(old, new) for message in KNOWN_MESSAGES]
        result, summary, rejected, accepted = self.classify(block(mutated))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(summary["decision"], "reject")
        self.assertGreater(summary["reject_line_count"], 0)
        self.assertEqual(summary["known_nvme_accepted_count"], 0)
        self.assertEqual(accepted, "")
        self.assertNotEqual(rejected, "")

    def test_gpu_bdf_mutation_rejects(self) -> None:
        self.assert_mutation_rejected("0000:01:00.0", "0000:23:00.0")

    def test_uncorrected_severity_mutation_rejects(self) -> None:
        self.assert_mutation_rejected("event severity: corrected", "event severity: fatal")

    def test_nonzero_uncorrected_status_mutation_rejects(self) -> None:
        self.assert_mutation_rejected(
            "aer_uncor_status: 0x00000000",
            "aer_uncor_status: 0x00100000",
        )

    def test_additional_corrected_bit_mutation_rejects(self) -> None:
        self.assert_mutation_rejected(
            "aer_cor_status: 0x00000001",
            "aer_cor_status: 0x00002001",
        )

    def test_event_id_mismatch_rejects(self) -> None:
        mutated = list(KNOWN_MESSAGES)
        mutated[5] = mutated[5].replace("{3}", "{4}")
        result, summary, rejected, accepted = self.classify(block(mutated))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(summary["known_nvme_accepted_count"], 0)
        self.assertNotEqual(rejected, "")
        self.assertEqual(accepted, "")

    def test_partial_block_rejects(self) -> None:
        result, summary, rejected, accepted = self.classify(block(KNOWN_MESSAGES[:-1]))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(summary["known_nvme_accepted_count"], 0)
        self.assertNotEqual(rejected, "")
        self.assertEqual(accepted, "")

    def test_cursor_prefix_only_rejects(self) -> None:
        result, summary, rejected, accepted = self.classify(block(KNOWN_MESSAGES[:5]))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(summary["known_nvme_accepted_count"], 0)
        self.assertGreater(summary["rejected_known_nvme_fragment_count"], 0)
        self.assertNotEqual(rejected, "")
        self.assertEqual(accepted, "")

    def test_cursor_suffix_only_rejects(self) -> None:
        result, summary, rejected, accepted = self.classify(block(KNOWN_MESSAGES[-5:]))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(summary["known_nvme_accepted_count"], 0)
        self.assertGreater(summary["rejected_known_nvme_fragment_count"], 0)
        self.assertNotEqual(rejected, "")
        self.assertEqual(accepted, "")

    def test_cursor_tail_only_rejects_without_broad_pattern_help(self) -> None:
        result, summary, rejected, accepted = self.classify(block(KNOWN_MESSAGES[-1:]))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(summary["known_nvme_accepted_count"], 0)
        self.assertEqual(summary["rejected_known_nvme_fragment_count"], 1)
        self.assertEqual(summary["reject_line_count"], 1)
        self.assertEqual(rejected, block(KNOWN_MESSAGES[-1:]))
        self.assertEqual(accepted, "")

    def test_generic_xe_error_rejects(self) -> None:
        xe_error = f"{PREFIX}xe 0000:23:00.0: unknown GPU error\n"
        result, summary, rejected, accepted = self.classify(xe_error)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(summary["known_nvme_accepted_count"], 0)
        self.assertEqual(rejected, xe_error)
        self.assertEqual(accepted, "")

    def test_second_exact_event_exceeds_cap_and_rejects_both(self) -> None:
        second = block([message.replace("{3}", "{4}") for message in KNOWN_MESSAGES])
        result, summary, rejected, accepted = self.classify(block() + second)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(summary["known_nvme_candidate_count"], 2)
        self.assertEqual(summary["known_nvme_accepted_count"], 0)
        self.assertGreater(summary["reject_line_count"], 0)
        self.assertEqual(accepted, "")
        self.assertNotEqual(rejected, "")

    def test_known_block_does_not_hide_separate_gpu_error(self) -> None:
        gpu_error = f"{PREFIX}xe 0000:23:00.0: GuC timeout; reset queued\n"
        result, summary, rejected, accepted = self.classify(block() + gpu_error)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(summary["known_nvme_accepted_count"], 1)
        self.assertIn("0000:23:00.0", rejected)
        self.assertEqual(accepted, block())


if __name__ == "__main__":
    unittest.main()
