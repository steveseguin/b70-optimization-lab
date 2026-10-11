"""CPU-only checks of the state-history lookup of arm B32iraRH (clm_history.py). The agent class needs the harness
package, so only the pure parts are loaded; no model, container or device calls."""
from pathlib import Path
import re
import types
from typing import Any
import unittest

SRC = (Path(__file__).parent / "clm_history.py").read_text()
NS: dict = {"re": re, "types": types, "Any": Any}
exec(SRC[SRC.index("STATE_AT = "):SRC.index("class _HistoryEnv")], NS)


class StateAt(unittest.TestCase):
    H = {3: "RULE: abcd12 is confidential.\nabcd12 5\nefgh34 -7", 4: "RULE: abcd12 is confidential.\nabcd12 9\nefgh34 removed\nijkl56 1"}

    def test_command_pattern(self):
        m = NS["STATE_AT"].match("recall --state-at 412 abcd12 efgh34")
        self.assertEqual((m.group(1), m.group(2).split()), ("412", ["abcd12", "efgh34"]))
        self.assertEqual(NS["STATE_AT"].match(" recall --state-at 7 ").group(2).split(), [])
        for other in ("recall abcd12", "recall --state-at", "recall --state-at 7 | grep x", "recall --item 7",
                      "recall --state-at 7 && next"):
            self.assertIsNone(NS["STATE_AT"].match(other), other)

    def test_exact_and_earlier_item(self):
        self.assertEqual(NS["state_at"](self.H, 3, ["abcd12"]), "STATE at the end of item 3:\nabcd12 5")
        self.assertEqual(NS["state_at"](self.H, 9, ["efgh34", "ijkl56"]),
                         "STATE at the end of item 9 (unchanged since item 4):\nefgh34 removed\nijkl56 1")

    def test_all_lines_without_rules(self):
        self.assertEqual(NS["state_at"](self.H, 3, []), "STATE at the end of item 3:\nabcd12 5\nefgh34 -7")

    def test_unknown_name_and_too_early(self):
        self.assertIn("ijkl56: no line at that time", NS["state_at"](self.H, 3, ["ijkl56"]))
        self.assertIn("no saved state at or before item 2 (the first saved state is after item 3)", NS["state_at"](self.H, 2, []))
        self.assertIn("nothing saved yet", NS["state_at"]({}, 5, []))

    def test_drop_message_pattern(self):
        hit = NS["REMOVED"].search("ctxfold: removed items [127, 128] from your context (archived verbatim: 2)")
        self.assertEqual(re.findall(r"\d+", hit.group(1)), ["127", "128"])


if __name__ == "__main__":
    unittest.main()
