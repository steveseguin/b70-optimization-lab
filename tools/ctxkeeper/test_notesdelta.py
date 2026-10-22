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


class Records(unittest.TestCase):
    def test_a_line_that_lists_entries_is_not_asked_about_part_by_part(self):
        notes = "RULES\n- none\nSTATE\nsaru45: 145\n/app/answers.json: does not exist yet"
        delta = {"rules": [], "changes": [("/app/answers.json", 'created with p1_1: 544, p1_2: \u221274, p1_3: "ferryman", p1_4: "protected"'),
                                          ("saru45", "145 + 5 = 150, 150 - 3 = 147")], "open": []}
        new, info = nd.apply_delta(notes, delta, {5, 3, 544}, strict=True, near={"saru45": {5, 3}})
        self.assertFalse([m for m in info["mismatch"] if "answers.json" in m], info["mismatch"])
        self.assertIn('/app/answers.json: created with p1_1: 544', new)
        self.assertEqual(new.count("answers.json"), 1)                          # one line, replaced, not one per entry
        self.assertIn("saru45: 147", new)
        packed = {"rules": [], "changes": [("saru45", "100, then 100 + 999 = 1099")], "open": []}
        _, info = nd.apply_delta(notes, packed, {999}, strict=True, near={"saru45": {999}})
        self.assertTrue(any("saru45" in m for m in info["mismatch"]), info)        # a counter's packed changes still are asked
        self.assertTrue(nd.is_record('added p2_1: -128, p2_2: -101'))
        self.assertFalse(nd.is_record("292 - 67 = 225, 225 + 3 = 228"))
        self.assertFalse(nd.is_record("opened at 117, set to -190 (item 5: up)"))


class Stamped(unittest.TestCase):
    def test_a_change_that_opens_with_its_item_is_the_change_of_the_name_after_it(self):
        reply = ("NEW RULES\n(none)\nCHANGES\n(item 820) jami27: 11 - 90 = -79\n(item 818: no counter changes)\n"
                 "- (items 821-822) cone77: removed\n(item 823) note on the weather\nOPEN\n(none)")
        d = nd.parse_delta(reply)
        self.assertEqual(d["changes"], [("jami27", "11 - 90 = -79 (item 820)"), ("cone77", "removed (items 821-822)"),
                                        ("(item", "823) note on the weather")])   # no name: as before
        new, info = nd.apply_delta("RULES\n- r\nSTATE\njami27: 11\ncone77: 4", d, {90}, strict=True, near={"jami27": {90}})
        self.assertIn("jami27: -79", new)
        self.assertIn("cone77: removed", new)
        self.assertNotIn("(item 820)", new.split("STATE")[1].split("\n")[1])
        self.assertEqual(nd.leading_reference("(item 5) abc1: 3"), "abc1: 3 (item 5)")
        self.assertEqual(nd.leading_reference("abc1: 3 (item 5)"), "abc1: 3 (item 5)")


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

    def test_a_line_without_a_value_keeps_the_held_number(self):
        """Campaign 31, 2026-10-17: "amount not yet known, must recall items 4/5" is a remark on the value, not a value."""
        notes = "RULES\n(none)\nSTATE\nqibape16: -267\nOPEN"
        near = {"qibape16": set(), nd.LOOSE: set()}
        new, info = nd.apply_delta(notes, {"changes": [("qibape16", "reversal pending, amount not yet known (items 4/5)")]},
                                   set(), strict=True, near=near)
        self.assertEqual(new.splitlines()[3], "qibape16: -267 (reversal pending, amount not yet known items 4/5)")
        self.assertEqual(info["mismatch"], [])
        self.assertEqual(nd.apply_delta(notes, {"changes": [("qibape16", "removed (item 5)")]})[0].splitlines()[3],
                         "qibape16: removed (item 5)")

    def test_checks(self):
        texts = ["ITEM 7/9 (UPDATE)\nabcd12 was opened at 402. efgh34 was set to one hundred. efgh34 gained five. "
                 "Next on the list was wxyz56. It was set to minus sixty-two. What does qq11 hold now?"]
        notes = "RULES\n(none)\nSTATE\nabcd12: -107\nefgh34: 9\nwxyz56: 1\nOPEN"
        names = ["abcd12", "efgh34", "wxyz56"]
        self.assertEqual(nd.identifiers_in(texts), names)                         # qq11 is only asked about
        self.assertEqual(nd.mention_counts(names + ["plain"], texts), {"abcd12": 1, "efgh34": 2, "wxyz56": 1})
        near = nd.numbers_near(names, texts)
        self.assertEqual({k: sorted(v) for k, v in near.items() if k != nd.LOOSE}, {"abcd12": [100, 402], "efgh34": [5, 100], "wxyz56": [-62]})
        self.assertEqual(near[nd.LOOSE], {"wxyz56"})                 # named in a sentence that states no number
        seen = nd.numbers_in(texts[0])
        ap = lambda changes: nd.apply_delta(notes, {"changes": changes}, seen, strict=True, near=near)[1]
        self.assertEqual(ap([("abcd12", "402"), ("wxyz56", "-62"), ("efgh34", "100 + 5 = 105")])["mismatch"], [])
        self.assertEqual(len(ap([("wxyz56", "62")])["mismatch"]), 1)             # the sign is part of a set value
        self.assertEqual(len(ap([("abcd12", "opened at 999")])["mismatch"]), 1)
        self.assertEqual(len(ap([("efgh34", "77")])["mismatch"]), 1)             # worked out, without working
        steps = ap([("abcd12", "402"), ("efgh34", "105")])["steps"]
        self.assertEqual(nd.under_accounted(nd.mention_counts(names, texts), steps),
                         ["efgh34 (mentioned 2 times, 1 changes written)", "wxyz56 (mentioned 1 times, 0 changes written)"])

    def test_a_set_written_after_the_old_value_is_stored_as_the_set(self):
        """Campaign 51 seed 0 (2026-10-21): `dobazi47: 53 set to -39 (item 169)` was stored as written. The keeper reads
        the last number (-39); the release audit and a plain reader take the first (53). The line is stored as the
        value the keeper accepted, with its remarks. `439 -> 10` was already followed as a set by chain_of; a bare
        item reference in brackets (`opened at 88 (816)`) is one number and stays as written."""
        texts = ["ITEM 169/300 (UPDATE)\ndobazi47 was set to minus thirty-nine. roxamo42 now stands at 10. mihini34 was opened at 7."]
        notes = "RULES\n(none)\nSTATE\ndobazi47: 53\nroxamo42: 439\nOPEN"
        names = ["dobazi47", "roxamo42", "mihini34"]
        near, seen = nd.numbers_near(names, texts), nd.numbers_in(texts[0])
        new, info = nd.apply_delta(notes, {"changes": [("dobazi47", "53 set to -39 (item 169)"), ("roxamo42", "439 -> 10"),
                                                       ("mihini34", "opened at 7 (169)")]}, seen, strict=True, near=near)
        self.assertEqual(new.splitlines()[3:6], ["dobazi47: -39 (item 169)", "roxamo42: 10", "mihini34: opened at 7 (169)"])
        self.assertEqual((info["mismatch"], info["restated_sets"]), ([], 1))

    def test_a_set_the_turns_state_that_no_line_takes_is_named(self):
        """Campaign 51 seed 0 / 49d seed 2 (2026-10-21): a stated set booked as a change, or skipped, with every amount
        stated near the name, passed every check. The set the turns state must appear in the name's lines or be the
        value held."""
        texts = ["ITEM 1079/1233 (UPDATE)\nThe clerk recorded didoyo44 at minus fourteen. Fourteen were taken from didoyo44. "
                 "roru25 was set to four hundred and forty-five. Next on the list was coco56. It was opened at 523. "
                 "What value does qq11 hold now?"]
        st = nd.sets_stated(["didoyo44", "roru25", "coco56", "qq11"], texts)
        self.assertEqual({k: sorted(v) for k, v in st.items()}, {"didoyo44": [-14], "roru25": [445], "coco56": [523]})
        notes = "RULES\n(none)\nSTATE\ndidoyo44: 474\nroru25: 349\ncoco56: 523\nOPEN"
        self.assertEqual(nd.sets_not_taken([("didoyo44", "488 - 14 = 474"), ("roru25", "263 + 86 = 349"), ("coco56", "opened at 523")], st, notes),
                         ['didoyo44: -14 ("The clerk recorded didoyo44 at minus fourteen.")',
                          'roru25: 445 ("roru25 was set to four hundred and forty-five.")'])
        self.assertEqual(nd.sets_not_taken([("didoyo44", "set to -14 (item 1079), then -14 - 14 = -28")], st, notes), [])
        # a name the NOTES hold as removed, reopened by the turns, with no line at all (campaign 54d: vonedi62)
        texts3 = ["ITEM 349/1233 (UPDATE)\nA new page was started for vonedi62, at minus one hundred and seventeen. como20 gained four."]
        notes3 = "RULES\n(none)\nSTATE\nvonedi62: removed (item 340)\ncomo20: 108\nOPEN"
        st3 = nd.sets_stated(["vonedi62", "como20"], texts3); rm3 = nd.removals_stated(["vonedi62", "como20"], texts3)
        self.assertEqual(nd.sets_not_taken([("como20", "104 + 4 = 108")], st3, notes3), [])                 # without the removals map: as before
        self.assertEqual(nd.sets_not_taken([("como20", "104 + 4 = 108")], st3, notes3, rm3),
                         ['vonedi62: -117 ("A new page was started for vonedi62, at minus one hundred and seventeen.")'])
        texts4 = ["ITEM 460/1233 (UPDATE)\nvonedi62 was opened at -57. Later that day vonedi62 was struck off the books."]
        st4 = nd.sets_stated(["vonedi62"], texts4); rm4 = nd.removals_stated(["vonedi62"], texts4)
        self.assertEqual(nd.sets_not_taken([], st4, "RULES\n(none)\nSTATE\nvonedi62: removed (item 389)\nOPEN", rm4), [])   # reopened and removed again: moot
        texts2 = ["ITEM 615/1233 (UPDATE)\nvonedi62 was struck off the books. Four went into como20."]
        notes2 = "RULES\n(none)\nSTATE\nvonedi62: 340\ncomo20: 108\nOPEN"
        self.assertEqual(nd.removals_not_taken([("vonedi62", "336 + 4 = 340 (item 610)"), ("como20", "104 + 4 = 108")], ["vonedi62", "como20"], texts2, notes2),
                         ['vonedi62: removed ("vonedi62 was struck off the books.")'])
        self.assertEqual(nd.removals_not_taken([("vonedi62", "removed (item 615, struck off the books)")], ["vonedi62"], texts2, "RULES\n(none)\nSTATE\nvonedi62: removed\nOPEN"), [])

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

    def test_a_third_lost_from_a_negative_value_moves_toward_zero(self):
        self.assertTrue(nd.third_loss_away_from_zero("-129 - 43 = -172 (item 274, 'lost a third of its value')", -129))
        self.assertTrue(nd.third_loss_away_from_zero("-51 - 17 (a third) = -68", -51))
        self.assertFalse(nd.third_loss_away_from_zero("-129 + 43 = -86 (item 274, 'lost a third of its value')", -129))
        self.assertFalse(nd.third_loss_away_from_zero("966 - 322 = 644 (lost a third, item 604)", 966))
        self.assertFalse(nd.third_loss_away_from_zero("-45 - 15 = -60 (item 20, 'lost 15')", -45))


if __name__ == "__main__":
    unittest.main()
