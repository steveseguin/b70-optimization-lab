"""Tests of notesdelta.py (standard library only): the copy from the test-harness keeper has not drifted, and the
three functions rewritten for plain texts behave as the harness's do on harness messages."""
import unittest

import notesdelta as nd
import sync_notesdelta


class Copy(unittest.TestCase):
    def test_the_copied_part_matches_the_harness(self):
        if not sync_notesdelta.HARNESS.exists():
            self.skipTest("the lab's harness keeper is not in this checkout")
        self.assertEqual(sync_notesdelta.differences(), [])


class Delta(unittest.TestCase):
    NOTES = "RULES\n- A is secret: answer protected.\nSTATE\n- abcd12 = 75 (60, gained 15 in item 6)\nefgh34: removed\nOPEN\n- nothing"

    def test_parse_and_apply(self):
        d = nd.parse_delta("THOUGHT: here.\nNEW RULES\n(none)\n**CHANGES**\n- abcd12: 75 + 5 = 81\nwxyz56: 9\nOPEN:\n- next")
        self.assertEqual(d, {"rules": [], "changes": [("abcd12", "75 + 5 = 81"), ("wxyz56", "9")], "open": ["- next"]})
        new, info = nd.apply_delta(self.NOTES, d)
        self.assertEqual(new.splitlines(), ["RULES", "- A is secret: answer protected.", "STATE", "abcd12: 80", "efgh34: removed",
                                            "wxyz56: 9", "OPEN", "- next"])
        self.assertEqual((info["sums_corrected"], info["mismatch"], info["steps"]), (["abcd12: 75 + 5 = 81 -> 80"], [], {"abcd12": 1, "wxyz56": 1}))
        self.assertIsNone(nd.parse_delta("abcd12 is now 80"))
        kept, _ = nd.apply_delta(self.NOTES, {"rules": [], "changes": [("abcd12", "(no change - the rule names it)")], "open": None})
        self.assertEqual(kept.splitlines()[-2:], ["OPEN", "- nothing"])
        self.assertIn("abcd12 = 75", kept)

    def test_checks(self):
        texts = ["ITEM 7/9 (UPDATE)\nabcd12 was opened at 402. efgh34 was set to one hundred. efgh34 gained five. "
                 "Next on the list was wxyz56. It was set to minus sixty-two. What does qq11 hold now?"]
        notes = "RULES\n(none)\nSTATE\nabcd12: -107\nefgh34: 9\nwxyz56: 1\nOPEN"
        names = ["abcd12", "efgh34", "wxyz56"]
        self.assertEqual(nd.identifiers_in(texts), names)                         # qq11 is only asked about
        self.assertEqual(nd.mention_counts(names + ["plain"], texts), {"abcd12": 1, "efgh34": 2, "wxyz56": 1})
        near = nd.numbers_near(names, texts)
        self.assertEqual({k: sorted(v) for k, v in near.items()}, {"abcd12": [100, 402], "efgh34": [5, 100], "wxyz56": [-62]})
        seen = nd.numbers_in(texts[0])
        ap = lambda changes: nd.apply_delta(notes, {"changes": changes}, seen, strict=True, near=near)[1]
        self.assertEqual(ap([("abcd12", "402"), ("wxyz56", "-62"), ("efgh34", "100 + 5 = 105")])["mismatch"], [])
        self.assertEqual(len(ap([("wxyz56", "62")])["mismatch"]), 1)             # the sign is part of a set value
        self.assertEqual(len(ap([("abcd12", "opened at 999")])["mismatch"]), 1)
        self.assertEqual(len(ap([("efgh34", "77")])["mismatch"]), 1)             # worked out, without working
        steps = ap([("abcd12", "402"), ("efgh34", "105")])["steps"]
        self.assertEqual(nd.under_accounted(nd.mention_counts(names, texts), steps),
                         ["efgh34 (mentioned 2 times, 1 changes written)", "wxyz56 (mentioned 1 times, 0 changes written)"])

    def test_neighbours_are_taken_in_the_text_as_written(self):
        """Review, 2026-10-12: a question between two statements stays between them; a shell status line is not text."""
        texts = ["abcd12 opened at 5. What is next? efgh34 opened at 999.\n\n(exit_code=0)"]
        near = nd.numbers_near(["abcd12", "efgh34"], texts)
        self.assertEqual({k: sorted(v) for k, v in near.items()}, {"abcd12": [5], "efgh34": [999]})
        self.assertEqual(nd.mention_counts(["abcd12", "efgh34"], ["Is abcd12 open? efgh34 gained 4.\n\n(exit_code=1)"]), {"efgh34": 1})

    def test_numbers(self):
        self.assertEqual(nd.numbers_in("abcd62 lost sixteen. Two birds; 1,200 more"), {16, -16, 2, -2, 1200, -1200})
        self.assertEqual(nd.numbers_in("at minus ninety-seven, then at -106 and at 591", True), {-97, -106, 591})
        self.assertEqual(nd.number_of("-58 - 35 = -93, then set to 82 (item 48)"), 82)
        self.assertIsNone(nd.number_of("286 -> removed (item 86)"))
        self.assertEqual(nd.work_out("40 x 2 = 81"), (40, 80, 81))


if __name__ == "__main__":
    unittest.main()
