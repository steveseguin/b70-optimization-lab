#!/usr/bin/env python3
"""Tests for the final-rule wording in make_sparse_prose_tasks.py (2026-10-18).

A stream with PROBE items must tell the model to add the final answers to /app/answers.json and keep the PROBE answers
already in it, in the rules, in the final item and after the stream ends (campaign 40: the model wrote a fresh file with
only the final counters). A stream without probes keeps the original words, and the wording never changes the stream.
No live services: the generator runs into a temporary directory.
"""
from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_sparse_prose_tasks as m

OPTS = {"words": True, "pronouns": False, "corrections": False, "plans": False, "relative": False}
KEEP = "keeping the PROBE answers already in it"


def build(tmp, name, probes_every):
    m.build(Path(tmp), name, 0, 0, 400, 3.0, 14, 40, "memory", OPTS, 3.9, None, 60, probes_every=probes_every,
            probes_k=3, rules=True)
    d = Path(tmp) / name
    stream = [json.loads(x) for x in (d / "environment" / "stream.jsonl").read_text().splitlines()]
    return ((d / "instruction.md").read_text(), stream, (d / "environment" / "end_text").read_text(),
            json.loads((d / "tests" / "spec.json").read_text()))


class FinalRule(unittest.TestCase):
    def test_probe_streams_say_keep_and_others_keep_the_old_words(self):
        with tempfile.TemporaryDirectory() as tmp:
            instr, stream, end, _spec = build(tmp, "probes", 10)
            self.assertTrue(any(it["kind"] == "PROBE" for it in stream))
            self.assertIn("When you have received the final item, add to /app/answers.json, " + KEEP, instr)
            self.assertNotIn("write /app/answers.json: a JSON object", instr)
            self.assertIn(KEEP, stream[-1]["last"])
            self.assertIn(KEEP, end)
            instr0, stream0, end0, _spec0 = build(tmp, "plain", 0)
            self.assertFalse(any(it["kind"] == "PROBE" for it in stream0))
            self.assertIn("When you have received the final item, write /app/answers.json: a JSON object mapping each\n"
                          "  listed counter to its current integer value", instr0)
            self.assertEqual(stream0[-1]["last"], "This was the last item. Write /app/answers.json now.")
            self.assertEqual(end0.strip(), "STREAM END: no more items. Answer the final query in /app/answers.json, then submit.")
            self.assertNotIn(KEEP, instr0 + end0)


if __name__ == "__main__":
    unittest.main()
