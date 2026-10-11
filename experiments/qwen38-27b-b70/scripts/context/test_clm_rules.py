"""CPU-only checks of the pinned RULE lines of arm B32iraR (clm_rules.py). The agent class needs the harness
package, so these tests load only the module's pure parts; no model, container or device calls."""
from pathlib import Path
import re
import unittest

SRC = (Path(__file__).parent / "clm_rules.py").read_text()
NS: dict = {}
exec(SRC.split("class ClmRulesAgent")[0].replace("import clm_improved as _ci", "")
     .replace("from clm_improved import ClmImprovedAgent", ""), NS)


class RuleLines(unittest.TestCase):
    def test_state_line_format(self):
        rx = re.compile(NS["STATE_LINE"])
        for ok in ("abcd12 5", "abcd12 -17", "abcd12 removed", "RULE: the counters abcd12 and efgh34 are confidential."):
            self.assertTrue(rx.match(ok), ok)
        for bad in ("abcd12 protected", "RULE:", "RULE:   ", "note: anything", "abcd12 -28-43", "rule: lower case"):
            self.assertFalse(rx.match(bad), bad)

    def test_rules_are_permanent(self):
        problem, old = NS["rules_problem"], "RULE: A is secret.\nabcd12 5"
        self.assertEqual(problem(old, "RULE: A is secret.\nRULE: tally = value x 5 + 13.\nabcd12 6", 12, 400), "")
        self.assertIn("removed or reworded", problem(old, "abcd12 6", 12, 400))
        self.assertIn("removed or reworded", problem(old, "RULE: A is very secret.\nabcd12 6", 12, 400))

    def test_rules_cannot_become_notes(self):
        problem = NS["rules_problem"]
        self.assertIn("more than 12", problem("", "\n".join(f"RULE: r{i}" for i in range(13)), 12, 400))
        self.assertIn("longer than 400", problem("", "RULE: " + "x" * 500, 12, 400))

    def test_protocol_anchor_exists(self):
        improved = (Path(__file__).parent / "clm_improved.py").read_text()
        self.assertEqual(improved.count(NS["ONLY_COUNTERS"]), 1)   # run() rewrites this phrase of PROTOCOL_READ


if __name__ == "__main__":
    unittest.main()
