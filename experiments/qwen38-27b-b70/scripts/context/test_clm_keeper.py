"""CPU-only checks of the pure parts of arm N32 (clm_keeper.py): item splitting, turn rendering, permanent RULES.
The agent class needs the harness package and litellm, so the module is not imported; no model or device calls."""
import json
from pathlib import Path
import re
from typing import Any
import unittest

SRC = (Path(__file__).parent / "clm_keeper.py").read_text()
NS: dict = {"json": json, "re": re, "Path": Path, "Any": Any, "base64": __import__("base64"), "types": __import__("types"), "__file__": str(Path(__file__).parent / "clm_keeper.py")}
exec(SRC[SRC.index("ARCH = "):SRC.index("class _KeeperEnv")], NS)


class Keeper(unittest.TestCase):
    def test_split_items(self):
        out = ("ITEM 3/9 (UPDATE)\nFirst report.\nMore.\n\nITEM 4/9 (PROBE)\nPROBE: answer now.\n\n"
               "ITEM 9/9 (QUERY)\nQUERY abcd12\n\n(exit_code=0)\n[context: 1 of 2]")
        self.assertEqual(NS["split_items"](out), {3: "First report.\nMore.", 4: "PROBE: answer now."})
        self.assertEqual(NS["split_items"]("STREAM END: no more items.\n\n(exit_code=0)"), {})

    def test_render_turns(self):
        turns = [{"role": "assistant", "content": "THOUGHT: fetch.", "reasoning_content": "abcd12 is 5 now",
                  "tool_calls": [{"function": {"name": "bash", "arguments": json.dumps({"command": "next"})}}]},
                 {"role": "tool", "content": "ITEM 1/9 (UPDATE)\ntext\n\n(exit_code=0)"},
                 {"role": "user", "content": "a nudge"}]
        self.assertEqual(NS["render_turns"](turns).splitlines()[:4],
                         ["ASSISTANT THINKING: abcd12 is 5 now", "ASSISTANT: THOUGHT: fetch.", "COMMAND: next",
                          "OUTPUT: ITEM 1/9 (UPDATE)"])
        self.assertTrue(NS["render_turns"](turns).endswith("NOTE: a nudge"))

    def test_rule_lines(self):
        notes = "RULES\n- A is secret: answer protected.\n* tally = value x 5 + 13\n\nSTATE:\nabcd12 5\nOPEN\n- nothing"
        self.assertEqual(NS["rule_lines"](notes), ["A is secret: answer protected.", "tally = value x 5 + 13"])
        self.assertEqual(NS["rule_lines"]("STATE\nabcd12 5"), [])

    def test_lost_rules_are_put_back(self):
        old = "RULES\n- A is secret: answer protected.\n- tally = value x 5 + 13\nSTATE\nabcd12 5"
        kept, lost = NS["keep_rules"](old, "RULES\n- tally  =  value x 5 + 13\nSTATE\nabcd12 9\nOPEN")
        self.assertEqual(lost, ["A is secret: answer protected."])                      # spacing may differ
        self.assertEqual(NS["rule_lines"](kept), ["A is secret: answer protected.", "tally  =  value x 5 + 13"])
        self.assertIn("abcd12 9", kept)
        _, lost = NS["keep_rules"](old, "RULES\n- a is secret: answer protected.\n- tally = value x 5 + 13\nSTATE")
        self.assertEqual(lost, ["A is secret: answer protected."])                      # a change of case is a change
        kept, lost = NS["keep_rules"](old, "STATE\nabcd12 9")          # the model dropped the whole section
        self.assertEqual(len(lost), 2)
        self.assertEqual(kept.splitlines()[0], "RULES")
        self.assertEqual(NS["keep_rules"](old, old), (old, []))

    def test_wants_thinking(self):
        w = NS["wants_thinking"]
        tool = lambda text, code=0: {"role": "tool", "content": f"{text}\n\n(exit_code={code})"}
        self.assertTrue(w([{"role": "user", "content": "task"}]))                         # nothing delivered yet
        pin = {"role": "user", "content": NS["PIN_HEAD"].format(n=12) + "\nRULES\n(none)\nSTATE\nabcd12: 5\nOPEN"}
        self.assertFalse(w([{"role": "user", "content": "task"}, pin]))                   # after a whole-context cut: routine
        self.assertFalse(w([tool("ITEM 3/9 (UPDATE)\nA quiet day. abcd12 went up by four.")]))
        self.assertTrue(w([tool("ITEM 4/9 (PROBE)\nPROBE: answer these questions now.\nASK p1_1: What value?")]))
        self.assertTrue(w([tool("ITEM 9/9 (QUERY)\nThe auditors ask.\nQUERY abcd12")]))
        self.assertTrue(w([tool("ITEM 3/9 (UPDATE)\ntext"), {"role": "user", "content": "CONTEXT LIMIT reached"}]))
        self.assertTrue(w([tool("bash: nope: command not found", 127)]))
        probe = tool("ITEM 4/9 (PROBE)\nASK p1_1: x")
        self.assertTrue(w([probe, {"role": "assistant", "content": ""}, tool('item 273: ASK p13_3: who?')]))   # question still open
        self.assertTrue(w([probe, {"role": "assistant", "content": "ok"}, tool("written")]))
        self.assertFalse(w([probe, {"role": "assistant", "content": "ok"}, tool("written"), {"role": "assistant", "content": ""},
                            tool("ITEM 5/9 (UPDATE)\nA quiet day.")]))                 # the next item closes it

    def test_recital(self):
        notes = "RULES\n- A is secret: answer protected.\nSTATE\nabcd12 5"
        ask = {"role": "tool", "content": "ITEM 4/9 (PROBE)\nPROBE: answer now.\nASK p1_1: What value does abcd12 hold?\n\n(exit_code=0)"}
        note = NS["recital"](notes, [{"role": "assistant", "content": ""}, ask])
        self.assertEqual(note["role"], "user")
        self.assertTrue(note["content"].startswith(NS["RECITE_HEAD"]))
        self.assertTrue(note["content"].endswith("- A is secret: answer protected."))
        self.assertIsNone(NS["recital"]("STATE\nabcd12 5", [ask]))                           # no rules to recite
        self.assertIsNone(NS["recital"](notes, [ask, note]))                                    # already recited
        self.assertIsNone(NS["recital"](notes, [{"role": "tool", "content": "ITEM 5/9 (UPDATE)\nA quiet day."}]))
        self.assertIsNotNone(NS["recital"](notes, [{"role": "tool", "content": "ITEM 9/9 (QUERY)\nQUERY abcd12"}]))

    def test_only_a_bare_next_is_a_verbatim_delivery(self):
        ok = NS["ONLY_NEXT"].fullmatch
        for cmd in ("next", " next ", "next && next", "next&&next && next"):
            self.assertTrue(ok(cmd), cmd)
        for cmd in ("next && echo DONE", "next; cat /app/answers.json", "next | head", "echo x && next", "nextx", ""):
            self.assertFalse(ok(cmd), cmd)

    def test_layout_check(self):
        ok = NS["has_layout"]
        self.assertTrue(ok("RULES\n- A is secret.\nSTATE\nabcd12 5\nOPEN"))
        self.assertTrue(ok("## RULES\n(none)\n\n**STATE:**\n- abcd12 = 5"))
        self.assertFalse(ok("ITEM 5/147:\n- abcd12 went up\n\nCurrent state:\n- abcd12 = 5\n\nContinuing."))
        self.assertFalse(ok("STATE\nabcd12 5\nRULES\n- late"))
        self.assertEqual(NS["rule_lines"]("## RULES\n(none)\n**STATE**\nabcd12 5"), [])
        self.assertEqual(NS["rule_lines"]("**RULES:**\n- A is secret.\n### STATE\nabcd12 5"), ["A is secret."])

    def test_text_before_the_rules_heading_is_dropped(self):
        self.assertEqual(NS["from_rules"]("THOUGHT: I need to rewrite the NOTES.\n\nRULES\n- A is secret.\nSTATE\nabcd12 5"),
                         "RULES\n- A is secret.\nSTATE\nabcd12 5")
        self.assertEqual(NS["from_rules"]("no heading here"), "no heading here")

    def test_request_puts_the_instruction_after_the_turns(self):
        text = NS["NOTES_REQUEST"].format(cap=2048, notes="(none yet)", turns="OUTPUT: ITEM 1/9 (UPDATE)\nx")
        self.assertLess(text.index("=== TURNS BEING MOVED OUT ==="), text.index("Write the new NOTES now"))
        self.assertTrue(text.rstrip().endswith("Output only the NOTES."))

    def test_lost_answers(self):
        lost = NS["lost_answers"]
        before = {"p1_1": 5, "p1_2": "the clerk"}
        self.assertEqual(lost(before, {"abcd12": 4}), before)                       # rewritten from scratch
        self.assertEqual(lost(before, {"p1_1": 7, "p2_1": 1}), {"p1_2": "the clerk"})   # a changed value is the agent's
        self.assertEqual(lost(before, {**before, "p2_1": 1}), {})
        self.assertEqual(lost(before, [1, 2]), {})                                  # not an object: left alone

    def test_repeat_guard(self):
        rep = NS["is_repeat"]
        self.assertTrue(rep('recall "p13_3"', 'recall "p13_3"', False))
        self.assertFalse(rep('recall "p13_3"', 'recall "p13_4"', False))
        self.assertFalse(rep("next", "next", True))                                 # a fetch is never a repeat
        self.assertFalse(rep("", "", False))
        self.assertIn("NOT RUN", NS["REPEAT_NOTE"])                                 # the words that turn thinking on
        self.assertEqual(NS["repeat_note"](1), NS["REPEAT_NOTE"])
        self.assertIn("5 times in a row", NS["repeat_note"](5))
        self.assertTrue(NS["QUESTION"].search(NS["repeat_note"](5)))                # still turns thinking on
        self.assertEqual([NS["loop_temperature"](n) for n in (0, 2, 3, 5, 20)], [None, None, 0.5, 0.7, 1.0])
        self.assertTrue(NS["QUESTION"].search(NS["REPEAT_NOTE"] + "\n\n(exit_code=75)"))

    def test_a_reworded_rule_comes_back_in_its_own_words_once(self):
        old = "RULES\n- Storage rule: stream contents only in my context; never redirect or tee next. Mirror file is context.\n- A is secret: answer protected.\nSTATE\nx"
        new = "RULES\n- Storage rule: stream contents only in my context; never redirect or tee next.\n- A is secret: answer protected.\n- Dates day first.\nSTATE\ny"
        kept, lost = NS["keep_rules"](old, new)
        self.assertEqual(len(lost), 1)
        self.assertEqual(NS["rule_lines"](kept), ["Storage rule: stream contents only in my context; never redirect or tee next. Mirror file is context.",
                                                   "A is secret: answer protected.", "Dates day first."])
        self.assertEqual(NS["keep_rules"](kept, kept), (kept, []))

    def test_numbers_in(self):
        n = NS["numbers_in"]("abcd12 was set to four hundred and two, then lost forty-nine. efgh34 came at -106; 1,200 more. "
                             "The bus was nine minutes late and one thousand two hundred and thirty-four gulls sat there.")
        for want in (402, 49, 106, -106, 1200, 9, 1234, -402):
            self.assertIn(want, n)
        self.assertNotIn(400, n)
        self.assertNotIn(2, n)
        self.assertEqual(NS["numbers_in"]("nothing here and there"), set())
        self.assertEqual(NS["numbers_in"]("ITEM 132/147 (UPDATE)\nabcd62 lost sixteen. v2_final stays."), {16, -16})

    def test_working_may_start_from_a_value_the_turns_set(self):
        notes = "RULES\n(none)\nSTATE\nabcd12: -31\nefgh34: removed\nOPEN"
        seen = NS["numbers_in"]("abcd12 was set to two hundred and ninety-four. It went up by twelve. efgh34 was opened at 75 and gained five.")
        new, info = NS["apply_delta"](notes, {"changes": [("abcd12", "294 + 12 = 306"), ("efgh34", "75 + 5 = 80")]}, seen)
        self.assertEqual(info["mismatch"], [])
        self.assertEqual(info["set_in_turns"], 2)
        self.assertIn("abcd12: 306", new)
        _, info = NS["apply_delta"](notes, {"changes": [("abcd12", "-13 + 12 = -1")]}, seen)       # from nowhere
        self.assertEqual(info["mismatch"], ["abcd12: working starts from -13, NOTES hold -31"])
        _, info = NS["apply_delta"](notes, {"changes": [("abcd12", "-31 + 12 = -19")]}, seen)
        self.assertEqual((info["mismatch"], info.get("set_in_turns", 0)), ([], 0))
        new, info = NS["apply_delta"](notes, {"changes": [("abcd12", "-31 \u2192 294"), ("abcd12", "294 + 12 = 306")]}, seen)
        self.assertEqual((info["mismatch"], new.splitlines()[3]), ([], "abcd12: 306"))       # an arrow line, then working from its value
        new, info = NS["apply_delta"]("RULES\n(none)\nSTATE\nabcd12: opened at 402\nOPEN", {"changes": [("abcd12", "400 + 5 = 405")]}, set())
        self.assertEqual(info["mismatch"], ["abcd12: working starts from 400, NOTES hold 402"])

    def test_split_turns(self):
        turn = lambda i, n: [{"role": "assistant", "content": f"a{i}"}, {"role": "tool", "content": "x" * n}]
        count = lambda msgs: sum(len(str(m["content"])) for m in msgs)
        turns = [m for i in range(11) for m in turn(i, 100)]                       # 11 turns of about 102
        self.assertEqual(NS["split_turns"](turns, count, 0), [turns])
        pieces = NS["split_turns"](turns, count, 650)
        self.assertEqual([len(p) // 2 for p in pieces], [6, 5])                    # two pieces of about equal size
        self.assertEqual([m for p in pieces for m in p], turns)                    # nothing lost, order kept
        self.assertTrue(all(p[0]["role"] == "assistant" for p in pieces))          # whole turns
        self.assertEqual(len(NS["split_turns"](turns, count, 5000)), 1)
        self.assertEqual([len(p) // 2 for p in NS["split_turns"](turns, count, 250)], [2, 2, 2, 2, 2, 1])
        lead = [{"role": "user", "content": "note"}] + turns[:4]
        self.assertEqual(NS["split_turns"](lead, count, 150)[0][0]["content"], "note")
        self.assertEqual(NS["split_turns"]([], count, 100), [[]])

    def test_unaccounted_names(self):
        tool = lambda text: {"role": "tool", "content": text + "\n\n(exit_code=0)"}
        turns = [{"role": "assistant", "content": ""}, tool("ITEM 31/147 (UPDATE)\nThe cook slept. xasa62 was removed from the ledger. It rained."),
                 {"role": "assistant", "content": ""}, tool("ITEM 32/147 (PROBE)\nPROBE: now.\nASK p1_1: What value does efgh34 hold now?"),
                 {"role": "assistant", "content": ""}, tool("item 12: mnop78 was set to four."),            # a search result, not a delivery
                 {"role": "assistant", "content": ""}, tool("ITEM 33/147 (UPDATE)\nabcd12 gained five. The build was late.")]
        names = ["abcd12", "xasa62", "efgh34", "mnop78", "build", "zz"]
        self.assertEqual(NS["unaccounted"](names, turns, [("abcd12", "5 + 5 = 10")]), ["xasa62"])
        self.assertEqual(NS["unaccounted"](names, turns, [("abcd12", "10"), ("xasa62", "removed")]), [])
        self.assertEqual(NS["unaccounted"](names, turns, []), ["abcd12", "xasa62"])
        self.assertEqual(NS["state_keys"]("RULES\n- r\nSTATE\nabcd12: 5\n- xasa62 = -152 (item 30)\nOPEN\n- o"), ["abcd12", "xasa62"])
        new, info = NS["apply_delta"]("RULES\n(none)\nSTATE\nabcd12: 5\nOPEN", {"changes": [("abcd12", "(no change)"), ("efgh34", "no change")]})
        self.assertEqual((new, info["changed"], info["added"]), ("RULES\n(none)\nSTATE\nabcd12: 5\nOPEN", 0, 0))
        new, info = NS["apply_delta"]("RULES\n(none)\nSTATE\nabcd12: 5\nOPEN", {"changes": [("abcd12", "(no change \u2014 mention is the confidentiality rule itself)")]})
        self.assertEqual((new, info["steps"]), ("RULES\n(none)\nSTATE\nabcd12: 5\nOPEN", {"abcd12": 1}))

    def test_changes_packed_onto_one_line_are_counted(self):
        n = NS["steps_in"]
        for value, want in (("578 + 62 = 640, then set to 174 (item 16)", 2), ("opened at 117, set to -190, +46 = -144 (item 39)", 3),
                            ("539 - 31 = 508 - 48 = 460, then removed (item 25)", 3), ("112 + 16 + 45 = 173 (item 539)", 2),
                            ("468 \u2212 19 = 449, set to 473 (item 449); +31 = 504 (item 450); set to 327 (item 454)", 4),
                            ("771 + 75 = 846 (item 455), removed (item 456, struck off the books)", 2),
                            ("451 \u2212 89 = 362 (item 453), \u2212 75 = 287 (item 454)", 2), ("reopened at 183, then +64 = 247", 2),
                            ("removed (item 150, struck off the books)", 1), ("set to -3", 1), ("402", 1), ("-107 \u2192 -31", 1),
                            ("uses argparse, reads the environment, writes a log", 1), ("1,234 + 6 = 1,240", 1),
                            ("-10 + 5 = -5", 1), ("\u221210 + 5 = \u22125, +7 = 2", 2), ("10 + (5) + 2 = 17 (item 3)", 2)):   # a signed start is no change
            self.assertEqual(n(value), want, value)
        notes = "RULES\n(none)\nSTATE\nabcd12: 578\nefgh34: removed\nOPEN"
        seen = NS["numbers_in"]("efgh34 was opened at 585. It went down by 79.")
        _, info = NS["apply_delta"](notes, {"changes": [("abcd12", "578 + 62 = 640, then set to 174"), ("efgh34", "585 - 79 = 506"),
                                                        ("ijkl56", "opened at 127, +5 = 132")]}, seen)
        self.assertEqual(info["steps"], {"abcd12": 2, "efgh34": 2, "ijkl56": 2})      # efgh34: the set it starts from, and the change

    def test_a_line_that_packs_several_changes_is_followed_part_by_part(self):
        c = NS["chain_of"]
        self.assertEqual(c("reopened at 183, then +64 = 247 (item 17)", None, {183}), (247, [183], 0))
        self.assertEqual(c("opened at 117, set to -190, +46 = -144 (item 39)", None, {117, -190}), (-144, [117, -190], 0))
        self.assertEqual(c("539 - 31 = 508 - 48 = 460, then removed (item 25)", 539, set()), (None, [], 0))
        self.assertEqual(c("36 \u2212 2 = 34, \u2212 76 = \u221242 (item 451); +40 = \u22122 (item 452)", 36, set()), (-2, [], 0))
        self.assertEqual(c("set to \u22123, then \u22123 + 39 = 36 (item 445)", 366, {-3}), (36, [-3], 0))
        self.assertEqual(c("3, set to 111 (item 452), +82 = 193 (item 454)", 3, {111}), (193, [111], 0))
        self.assertEqual(c("585 - 79 = 506, then removed", None, {585}), (None, [585], 1))     # the set opens the working
        self.assertEqual(c("opened at 79 (item 521, reopened after removal at 296); 79 \u2212 79 = 0 (item 523)", None, {79}), (0, [79], 0))
        # an arrow separates parts; a wrong sum is recomputed and the next part may start from it as written (X32p at 1M)
        self.assertEqual(c("279 \u2192 415 (set, item 582), then 415 - 18 = 397, then removed (item 587)", 279, {415}), (None, [415], 0))
        self.assertEqual(c("461 \u2192 26 (recorded at, item 584), then 26 + 82 = 108", 461, {26}), (108, [26], 0))
        self.assertEqual(c("438 \u2212 56 = 382, then set to \u221255 (382 \u2192 \u221255)", 438, {-55}, {56}), (-55, [-55], 0))   # a remark with an arrow
        self.assertEqual(c("517 -> 164 (item 137), then 164 + 76 + 85 = 325 (item 139), then 325 + 18 = 343", 517, {164}), (343, [164], 0))
        # one wrong sum is redone: the last of the line, from the value so far, with stated amounts (X32p at 1M)
        fixed = []
        self.assertEqual(c("522 - 20 = 502, 502 - 17 = 485, 485 + 58 = 498 (item 442)", 522, set(), {20, 17, 58}, fixed), (543, [], 0))
        self.assertEqual(fixed, ["485 + 58 = 498 -> 543"])
        self.assertIsNone(c("522 - 20 = 502, 502 - 17 = 485, 485 + 58 = 498", 522, set(), {20, 17}))      # 58 is nowhere
        self.assertIsNone(c("522 - 20 = 502, 502 - 17 = 485, 485 + 58 = 498", 522, {498}, {20, 17, 58}))  # 498 is stated: a set?
        self.assertIsNone(c("522 - 20 = 502, 502 - 17 = 485, +58 = 498", 522, set(), {20, 17, 58}))       # not from the value so far
        # a wrong sum anywhere else is asked about, whatever comes after it; brackets belong to the sum (17, not 12)
        self.assertIsNone(c("10 + (5) + 2 = 12, then +1 = 13", 10, {5, 2, 1}))
        self.assertIsNone(c("10 + (5) + 2 = 12, then 12 + 1 = 13", 10, {5, 2, 1}))
        self.assertEqual(c("10 + (5) + 2 = 17, then 17 + 1 = 18", 10, {5, 2, 1}), (18, [], 0))
        self.assertIsNone(c("set to 600, then 600 + 63 = 664, then 664 - 4 = 660", -120, {600}))
        self.assertEqual(c("set to 600, then 600 + 63 = 663, then 663 - 4 = 659", -120, {600}), (659, [600], 0))
        for value, held, stated in (("set to 600, then 600 + 63 = 663", -120, set()),            # 600 is not in the turns
                                    ("opened at 117, +46 = 163, about right", None, {117}),      # a part without a number
                                    ("-20 \u2192 set to -159, then -2 \u2192 -161", -20, {-159}),  # arrows are not followed
                                    ("7 / 2 = 3, then set to 9", 7, {9}), ("480 + 5 = 485", 480, set()), ("removed", 5, set()),
                                    ("increased by 5, then +2 = 7", 10, {5, 2}),                 # a change in words is not a set
                                    ("answered 571, then 12", None, {571, 12}), ("set to 5, set to 7, set to 5", 1, {5, 7})):   # a set is good once
            self.assertIsNone(c(value, held, stated), value)
        notes = "RULES\n(none)\nSTATE\nabcd12: 36\nefgh34: removed\nmnop78: 9\nOPEN"
        turns = "ITEM 17/147 (UPDATE)\nabcd12 lost 2. Seventy-six were taken from abcd12. efgh34 came back onto the books at 183. efgh34 gained sixty-four. wxyz56 was opened at 585. wxyz56 went down by 79. wxyz56 was struck off."
        seen = NS["numbers_in"](turns)
        ap = lambda changes: NS["apply_delta"](notes, {"changes": changes}, seen, strict=True, near=NS["numbers_near"](["abcd12", "efgh34", "wxyz56", "mnop78"], [{"role": "tool", "content": turns}]))
        new, info = ap([("abcd12", "36 - 2 = 34, - 76 = -42 (item 451)"), ("efgh34", "reopened at 183, then +64 = 247 (item 17)"),
                        ("wxyz56", "585 - 79 = 506, then removed"), ("mnop78", "set to 600, then 600 + 63 = 663")])
        self.assertEqual(new.splitlines()[3:7], ["abcd12: -42", "efgh34: 247", "mnop78: set to 600, then 600 + 63 = 663", "wxyz56: removed"])
        self.assertEqual((info["chained"], info["mismatch"]), (3, ["mnop78: 663 is not a value the turns state; write the working from the value the NOTES hold, 9"]))
        self.assertEqual(info["steps"], {"abcd12": 2, "efgh34": 2, "wxyz56": 3, "mnop78": 2})
        _, loose = NS["apply_delta"](notes, {"changes": [("abcd12", "36 - 2 = 34, - 76 = -42")]}, seen)       # only with the strict checks
        self.assertNotIn("chained", loose)

    def test_amounts_in_working_must_be_stated_for_the_thing(self):
        """Working that adds up and starts from the value held can still be made up (X32m at 1M: "recorded katu85 at
        five hundred and twenty-three" came back as `650 - 27 = 623`)."""
        ok = NS["amounts_ok"]
        self.assertTrue(ok(" - 27", {27}) and ok(" + 16 + 45", {-16, 45}) and ok(" - 27", None) and ok("", set()))
        self.assertFalse(ok(" - 27", {523, 52, 17}) or ok(" + 16 + 45", {16}))
        tool = lambda text: {"role": "tool", "content": text + "\n\n(exit_code=0)"}
        turns = [tool("ITEM 246/617 (UPDATE)\nThe clerk recorded katu85 at five hundred and twenty-three. wxyz56 gained 52, and then 17 more.")]
        notes = "RULES\n(none)\nSTATE\nkatu85: 650\nwxyz56: 100\nOPEN"
        near, seen = NS["numbers_near"](["katu85", "wxyz56"], turns), NS["numbers_in"](turns[0]["content"])
        ap = lambda changes, **kw: NS["apply_delta"](notes, {"changes": changes}, seen, strict=True, **kw)[1]["mismatch"]
        self.assertEqual(ap([("katu85", "650 - 27 = 623 (item 246)")], near=near),
                         ["katu85: `650 - 27 = 623 (item 246)` adds or takes an amount the turns do not state for it; read the item again"])
        self.assertEqual(ap([("katu85", "650 - 27 = 623 (item 246)")]), [])                    # only with the near check
        self.assertEqual(ap([("katu85", "523"), ("wxyz56", "100 + 52 + 17 = 169")], near=near), [])
        self.assertEqual(ap([("wxyz56", "100 + 52 = 152, then +18 = 170")], near=near),          # a packed line with a made-up amount
                         ["wxyz56: 170 is not a value the turns state; write the working from the value the NOTES hold, 100"])
        self.assertEqual(ap([("wxyz56", "99 + 1 = 100")], near=near), [])                         # noted before: no question at all
        # a line of several parts that cannot be followed is not asked about an "amount" that is one of its own results
        packed = "100 \u2192 164 (item 137), then 164 + 52 + 17 = 233 (item 139), then 233 + 52 = 285 (item 144)"
        self.assertFalse([m for m in ap([("wxyz56", packed)], near=near) if "adds or takes" in m])

    def test_an_amount_may_be_another_things_value_or_a_small_factor(self):
        """The hard stream: "went up by as much as bamo35 held at that moment", "was doubled". The amount is another
        thing's value, or a factor said in words (N32nr, hard seed 1: every such line was questioned)."""
        ok = NS["amounts_ok"]
        self.assertTrue(ok(" * 2", set()) and ok(" / 2", {5}) and ok(" x 3", set()) and ok(" + 577", {577}))
        self.assertFalse(ok(" + 2", set()) or ok(" * 27", set()) or ok(" - 27", {523}))
        tool = lambda text: {"role": "tool", "content": text + "\n\n(exit_code=0)"}
        turns = [tool("ITEM 32/147 (UPDATE)\nAttention then turned to vohihi44. It went up by as much as bamo35 held at that moment. "
                      "bamo35 lost 7. sajaro19 was doubled. mosu40 went up by as much as bamo35 held at that moment.")]
        notes = "RULES\n(none)\nSTATE\nvohihi44: 228\nbamo35: 577\nsajaro19: 549\nmosu40: 392\nOPEN"
        names = ["vohihi44", "bamo35", "sajaro19", "mosu40"]
        near, seen = NS["numbers_near"](names, turns), NS["numbers_in"](turns[0]["content"])
        ap = lambda changes: NS["apply_delta"](notes, {"changes": changes}, seen, strict=True, near=near)
        new, info = ap([("vohihi44", "228 + 577 = 805"), ("bamo35", "577 - 7 = 570"), ("sajaro19", "549 * 2 = 1098"),
                        ("mosu40", "392 + 570 = 962")])
        self.assertEqual(info["mismatch"], [])
        self.assertEqual(new.splitlines()[3:7], ["vohihi44: 805", "bamo35: 570", "sajaro19: 1098", "mosu40: 962"])
        _, info = ap([("vohihi44", "228 + 578 = 806")])                             # nobody holds 578
        self.assertEqual(len(info["mismatch"]), 1)
        _, info = ap([("bamo35", "577 - 7 = 570"), ("mosu40", "392 + 577 = 969")])    # the value bamo35 held before its change: also held
        self.assertEqual(info["mismatch"], [])

    def test_review_findings_of_code_state_p(self):
        """Each of these stored a wrong value, or lost a right one, before it ran (read-only review, 2026-10-12)."""
        tool = lambda text: {"role": "tool", "content": text + "\n\n(exit_code=0)"}
        turns = [tool("ITEM 9/147 (UPDATE)\nabcd12 gained 5. vohi44 went up by as much as bamo35 held at that moment. katu85 was recorded at 523.")]
        notes = "RULES\n(none)\nSTATE\nabcd12: 70\nvohi44: 228\nbamo35: 402\nkatu85: 650\nzzzz99: 27\nOPEN"
        names = ["abcd12", "vohi44", "bamo35", "katu85", "zzzz99"]
        near, seen = NS["numbers_near"](names, turns), NS["numbers_in"](turns[0]["content"])
        ap = lambda changes: NS["apply_delta"](notes, {"rules": [], "open": None, "changes": changes}, seen, strict=True, near=near)
        # 1. leaving out one made-up line must not leave the next one standing on it
        for lines in ([("abcd12", "70 - 27 = 43"), ("abcd12", "43 - 31 = 12")], [("abcd12", "70 + 5 = 75"), ("abcd12", "75 - 27 = 48")]):
            kept, left = NS["without_doubtful"](notes, {"rules": [], "open": None, "changes": lines}, seen, True, near)
            new, _ = NS["apply_delta"](notes, kept, seen, strict=True, near=near)
            self.assertIn(new.splitlines()[3], ("abcd12: 70", "abcd12: 75"), lines)
            self.assertNotIn("abcd12: 12", new)
        # 2. a name the NOTES hold is never taken for another name misspelled
        delta = {"rules": [], "open": None, "changes": [("bako35", "40 + 5 = 45")]}
        self.assertEqual(NS["respell"](delta, {"bamo35": 1}, ["bako35", "bamo35"])[1], {})
        self.assertEqual(NS["respell"](delta, {"bamo35": 1})[1], {"bako35": "bamo35"})        # unknown to the NOTES: a misspelling
        # 4. an amount is not excused by a value that a thing these turns never mention happens to hold (zzzz99: 27)
        self.assertEqual(len(ap([("katu85", "650 - 27 = 623")])[1]["mismatch"]), 1)
        self.assertEqual(ap([("vohi44", "228 + 402 = 630")])[1]["mismatch"], [])              # bamo35 is mentioned: its value counts
        # 4b. the amounts of a packed line do not become values that later lines may use (its sets and its result do)
        turns2 = [tool("ITEM 9/147 (UPDATE)\nabcd12 gained 27. abcd12 was set to 174. katu85 was recorded at 523.")]
        notes2 = "RULES\n(none)\nSTATE\nabcd12: 578\nkatu85: 650\nOPEN"
        near2, seen2 = NS["numbers_near"](["abcd12", "katu85"], turns2), NS["numbers_in"](turns2[0]["content"])
        ap2 = lambda changes: NS["apply_delta"](notes2, {"rules": [], "open": None, "changes": changes}, seen2, strict=True, near=near2)[1]["mismatch"]
        self.assertEqual(len(ap2([("abcd12", "578 + 27 = 605, then set to 174"), ("katu85", "650 - 27 = 623")])), 1)
        self.assertEqual(ap2([("abcd12", "578 + 27 = 605, then set to 174"), ("katu85", "650 - 174 = 476")]), [])   # 174: abcd12 holds it now
        # 5. a name written into the working is not an amount
        self.assertEqual(ap([("vohi44", "228 + 402 (bamo35) = 630")])[1]["mismatch"], [])
        self.assertTrue(NS["amounts_ok"](" + 402 (bamo35's value)", {402}) and not NS["amounts_ok"](" + 35", {402}))

    def test_an_open_question_is_found_until_the_next_delivery(self):
        tool = lambda text: {"role": "tool", "content": text}
        ask = tool("ITEM 609/618 (PROBE)\nPROBE: answer these questions now.\nASK p29_1: What value does javo77 hold now?")
        body = [{"role": "assistant", "content": "next"}, tool("ITEM 608/618 (UPDATE)\ntext"), {"role": "assistant", "content": ""}, ask,
                {"role": "user", "content": "[[RULES in force]] - a rule"}, {"role": "assistant", "content": "", "tool_calls": []},
                tool("ITEM 468 (archived)\nketaqi61 now stands at 12."), {"role": "assistant", "content": ""}, tool("item 36: diro90 gained six.")]
        self.assertEqual(NS["open_question"](body), 3)                              # recall output does not close it
        self.assertIsNone(NS["open_question"](body + [{"role": "assistant", "content": ""}, tool("ITEM 610/618 (UPDATE)\nmore text")]))
        self.assertIsNone(NS["open_question"](body[:2]))
        # an archived question item printed by `recall --item N` is not a question that was asked now
        old = tool("ITEM 441 (archived)\nPROBE: answer these questions now.\nASK p21_1: What value does faxamo72 hold now?")
        self.assertIsNone(NS["open_question"](body[:2] + [{"role": "assistant", "content": ""}, old]))
        self.assertEqual(NS["open_question"](body + [{"role": "assistant", "content": ""}, old]), 3)

    def test_the_ordinary_cut_keeps_an_open_question_and_lets_go_of_an_answered_one(self):
        tool = lambda text: {"role": "tool", "content": text}
        ask = tool("ITEM 609/618 (PROBE)\nPROBE: answer these questions now.\nASK p29_1: What value does javo77 hold now?")
        fetch = [{"role": "assistant", "content": ""}, tool("ITEM 468 (archived)\nketaqi61 now stands at 12.")]
        body = [{"role": "assistant", "content": "next"}, tool("ITEM 608/618 (UPDATE)\ntext"), {"role": "assistant", "content": ""}, ask] + fetch * 3
        kept = NS["kept_question"](body, 6)                                          # the cut takes the question item
        self.assertEqual(len(kept), 1)
        self.assertEqual((kept[0]["role"], kept[0]["content"]), ("user", NS["OPEN_QUESTION"] + "\n" + ask["content"]))
        self.assertEqual(NS["kept_question"](body, 3), [])                           # the cut stops before it: nothing to keep
        self.assertEqual(NS["kept_question"](body[:2], 2), [])                       # no question open
        view = kept + fetch * 2                                                      # as it stands after the cut
        self.assertEqual(NS["open_question"](view), 0)
        self.assertFalse(NS["answered_copy"](view))
        self.assertEqual(NS["kept_question"](view, 3), kept)                         # cut again: the same text, the head not doubled
        self.assertTrue(NS["wants_thinking"]([{"role": "system", "content": "s"}, {"role": "user", "content": "task"}] + view))
        moved_on = view + [{"role": "assistant", "content": ""}, tool("ITEM 610/618 (UPDATE)\nmore text\n\n(exit_code=0)")]
        self.assertTrue(NS["answered_copy"](moved_on))
        self.assertFalse(NS["answered_copy"](moved_on[1:]))

    def test_recall_shows_the_nearest_matches_and_counts_first(self):
        import subprocess, sys, tempfile
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        arch = Path(d.name) / "archive"
        arch.mkdir()
        for i in list(range(1, 61)) + [1000, 1001]:                                  # file names sort wrongly from item 1000 on
            (arch / f"item-{i:03d}.txt").write_text(f"The fog lifted. diro90 was set to {i * 3}. It rained.\n\nThe cook slept.")
        tool = Path(d.name) / "recall.py"
        tool.write_text((Path(__file__).parent / "recall.py").read_text().replace('D = "/tmp/.live_ctx/archive"', f'D = "{arch}"'))
        run = lambda *a: subprocess.run([sys.executable, str(tool), *a], capture_output=True, text=True).stdout.strip().splitlines()
        out = run("diro90", "--before", "48")
        self.assertEqual(out[0], "[48 matches; showing the 40 nearest before item 48; 8 earlier ones are not shown: narrow with --after N]")
        self.assertEqual((out[1], out[-1], len(out)), ("item 9: diro90 was set to 27. It rained.", "item 48: diro90 was set to 144. It rained.", 41))
        self.assertEqual(run("diro90", "--before=48"), out)
        out = run("diro90")
        self.assertTrue(out[0].startswith("[62 matches; showing the newest 40; 22 earlier ones are not shown"))
        self.assertEqual(out[-2:], ["item 1000: diro90 was set to 3000. It rained.", "item 1001: diro90 was set to 3003. It rained."])
        out = run("diro90", "--after", "5", "--max-lines", "3")
        self.assertEqual(out, ["[58 matches; showing the first 3 from item 5 on; 55 later ones are not shown: narrow with --before N]",
                               "item 5: diro90 was set to 15. It rained.", "item 6: diro90 was set to 18. It rained.", "item 7: diro90 was set to 21. It rained."])
        self.assertEqual(run("diro90", "--after", "59", "--before", "60"), ["item 59: diro90 was set to 177. It rained.", "item 60: diro90 was set to 180. It rained."])
        self.assertEqual(run("zebra", "--before", "9"), ["recall: no archived sentence matches 'zebra' up to item 9"])
        self.assertEqual(run("--item", "7")[:2], ["ITEM 7 (archived)", "The fog lifted. diro90 was set to 21. It rained."])

    def test_codex_findings_on_the_chain_and_the_filter(self):
        """Each stored a wrong value without a question, or kept one after it was questioned (Codex, 2026-10-12)."""
        tool = lambda text: {"role": "tool", "content": "ITEM 9/147 (UPDATE)\n" + text + "\n\n(exit_code=0)"}
        def run(held, said, reply):
            turns = [tool(said)]
            notes = f"RULES\n(none)\nSTATE\nabcd12: {held}\nOPEN"
            near, seen = NS["numbers_near"](["abcd12"], turns), NS["numbers_in"](turns[0]["content"])
            delta = {"rules": [], "open": None, "changes": [("abcd12", reply)]}
            new, info = NS["apply_delta"](notes, delta, seen, strict=True, near=near)
            kept, left = NS["without_doubtful"](notes, delta, seen, True, near)
            after, _ = NS["apply_delta"](notes, kept, seen, strict=True, near=near)
            return new.splitlines()[3], info["mismatch"], left, after.splitlines()[3]
        # 1. a removal, then a reopening at the number the working ended on: the reopening counts
        line, bad, _, _ = run(10, "abcd12 gained five. abcd12 was removed. abcd12 was reopened at fifteen.", "10 + 5 = 15, then removed, then reopened at 15")
        self.assertEqual((line, bad), ("abcd12: 15", []))
        line, bad, _, after = run(100, "abcd12 gained five. abcd12 was set to 112.", "100 + 5 = 112, then set to 112")
        self.assertEqual((len(bad), NS["number_of"](after.split(": ", 1)[1])), (1, 112))      # a wrong sum mid-line: asked; the line's own end stands
        # 2. a negative value set and then changed is not "minus twenty from the value held"
        line, bad, _, _ = run(10, "abcd12 was set to minus twenty. abcd12 gained five.", "-20 + 5 = -15, then -15")
        self.assertEqual((line, bad), ("abcd12: -15", []))
        line, bad, _, _ = run(10, "abcd12 gained five.", "-20 + 5 = -15")                 # -20 is nowhere: asked about
        self.assertEqual(len(bad), 1)
        self.assertEqual(run(451, "abcd12 lost 89. abcd12 went down by 75.", "451 - 89 = 362, - 75 = 287")[:2], ("abcd12: 287", []))   # `- 75` alone goes on
        # 3. a made-up amount is not let through by writing the value held in front of it
        line, bad, left, after = run(100, "abcd12 gained five.", "100, then 100 + 999 = 1099")
        self.assertEqual(len(bad), 1)
        # 4. a number the turns state as an amount is not a result that excuses the working: asked about. (It is not
        #    left out afterwards: working that ends on a number the turns state may be a set written as working.)
        line, bad, left, after = run(100, "abcd12 gained five.", "100 - 95 = 5")
        self.assertEqual((len(bad), left), (1, []))
        # 5. `old -> new` to a number that is nowhere is left out after the second reply
        line, bad, left, after = run(100, "abcd12 gained five.", "100 \u2192 999")
        self.assertEqual((len(bad), left, after), (1, ["abcd12: 100 \u2192 999"], "abcd12: 100"))
        # a sum is redone only when the working starts from the value so far; `+46 = 163` after a wrong reading is not "corrected"
        self.assertIsNone(NS["chain_of"]("opened at 117, +46 = 173", None, {117}))
        self.assertEqual(NS["chain_of"]("opened at 117, +46 = 163", None, {117}), (163, [117], 0))

    def test_second_review_of_the_chain_and_the_filter(self):
        """Six more ways to a wrong value (Codex, second pass on 2026-10-12): each is now right, or asked about and
        then left as the reply wrote it; none is put right by guessing."""
        tool = lambda text: {"role": "tool", "content": "ITEM 9/147 (UPDATE)\n" + text + "\n\n(exit_code=0)"}
        def run(held, said, *lines):
            turns = [tool(said)]
            notes = f"RULES\n(none)\nSTATE\nabcd12: {held}\nOPEN"
            near, seen = NS["numbers_near"](["abcd12"], turns), NS["numbers_in"](turns[0]["content"])
            delta = {"rules": [], "open": None, "changes": [("abcd12", v) for v in lines]}
            _, info = NS["apply_delta"](notes, delta, seen, strict=True, near=near)
            kept, left = NS["without_doubtful"](notes, delta, seen, True, near)
            after, _ = NS["apply_delta"](notes, kept, seen, strict=True, near=near)
            return len(info["mismatch"]), info["mismatch_at"], left, NS["number_of"](after.splitlines()[3].split(": ", 1)[1])
        # 1. an arrow inside a remark does not switch the amount check off
        self.assertEqual(run(100, "abcd12 gained five.", "100 - 95 = 5 (100 -> 5)")[:2], (1, [0]))
        # 2. `-3 = -6` after a set to -3 takes three away; it is not the value written again
        self.assertEqual(run(10, "abcd12 was set to -3. abcd12 lost 3.", "set to -3, then -3 = -6"), (0, [], [], -6))
        # 3. the line that is left out is the one that was questioned, not the first of that name
        self.assertEqual(run(10, "abcd12 was set to 20.", "10 -> 20", "10"), (1, [1], ["abcd12: 10"], 20))
        # 4. a wrong sum followed by its own result, where the turns set that number: asked, and the set stands
        self.assertEqual(run(10, "abcd12 gained 5. abcd12 was set to 16.", "10 + 5 = 16, then 16"), (1, [0], [], 16))
        self.assertEqual(run(10, "abcd12 gained 5. abcd12 was set to 16.", "10 + 5 = 16")[:3], (1, [0], []))      # the same on a plain line
        self.assertEqual(run(10, "abcd12 gained 5.", "10 + 5 = 16"), (0, [], [], 15))                            # a plain miscount is redone
        # 5. a set written as working is asked about, and kept: its result is a number the turns state for the thing
        self.assertEqual(run(436, "abcd12 was recorded at 514.", "436 + 78 = 514"), (1, [0], [], 514))
        self.assertEqual(run(650, "abcd12 was recorded at 523.", "650 - 27 = 623"), (1, [0], ["abcd12: 650 - 27 = 623"], 650))   # neither 27 nor 623: out
        # 6. a thing set to one value twice in a line: asked (known cost), nothing lost
        self.assertEqual(run(10, "abcd12 was set to 20. abcd12 gained 5. abcd12 was set to 20.", "set to 20, then 20 + 5 = 25, set to 20"), (1, [0], [], 20))
        # third pass: a line goes with a left-out line only when it comes after it
        self.assertEqual(run(10, "abcd12 gained five. abcd12 gained five.", "15 + 5 = 20", "15"), (2, [0, 1], ["abcd12: 15"], 20))
        self.assertEqual(run(10, "abcd12 gained 5.", "10 + 5 = 15", "15 - 84 = -69", "-69 + 5 = -64")[2:], (["abcd12: 15 - 84 = -69", "abcd12: -69 + 5 = -64"], 15))
        # `(5 x 2)` is part of the sum; a remark where an amount should be leaves a hole, and that is not a sum
        self.assertEqual(run(10, "abcd12 gained five twice, then gained one.", "10, then 10 + (5 x 2) + 1 = 21"), (0, [], [], 21))
        self.assertEqual(run(10, "abcd12 gained five, then gained one.", "10, then 10 + (five more) + 1 = 16")[:2], (1, [0]))
        self.assertEqual(NS["steps_in"]("10, then 10 + (5 x 2) + 1 = 21"), 4)
        # a minus sign standing apart is not dropped: `reopened at - 3` is not a set to 3
        self.assertEqual(run(10, "abcd12 lost 3. abcd12 was removed. abcd12 was reopened at minus three.", "10 - 3 = 7, then removed, then reopened at - 3")[:2], (1, [0]))
        self.assertEqual(run(10, "abcd12 lost 3. abcd12 was removed. abcd12 was reopened at minus three.", "10 - 3 = 7, then removed, then reopened at -3"), (0, [], [], -3))
        # fourth pass: no sum is redone where a remark stood, or where there is no sum; each is asked about
        for held, said, line in ((10, "abcd12 gained five more and then lost 1.", "10, then 10 + (five more) - 1 = 14"),
                                 (10, "abcd12 lost five and then lost 1.", "10, then 10 - (five) - 1 = 4"),
                                 (10, "abcd12 lost 5 twice and then lost 1.", "10, then 10 - (5 X 2) - 1 = -1"),
                                 (10, "abcd12 was opened at 10. abcd12 gained five.", "opened at 10, then 10 (gained five) = 15"),
                                 (10, "abcd12 gained 2 and was then doubled.", "10, then 10 + 2 (then doubled) = 24")):
            self.assertEqual(run(held, said, line)[:3], (1, [0], []), line)
        self.assertEqual(run(10, "abcd12 gained 2 and was then doubled.", "10, then 10 + 2 (then doubled) = 24")[3], 24)    # as the reply wrote it
        self.assertEqual(run(10, "abcd12 gained 5 and then gained 2.", "10, then 10 + 5 (item 3) + 2 = 17"), (0, [], [], 17))   # a remark beside a right sum
        # words with a hyphen, and marks round a number, are not "something left over"
        self.assertEqual(run(10, "abcd12 was removed. abcd12 was reopened at 3.", "removed, then re-opened at 3"), (0, [], [], 3))
        self.assertEqual(run(10, "abcd12 was reset to 5. abcd12 gained 3.", "re-set to 5, then 5 + 3 = 8"), (0, [], [], 8))
        self.assertEqual(run(10, "abcd12 gained 3. abcd12 was set to 5.", "10 + 3 = 13, then set to **5**"), (0, [], [], 5))
        self.assertEqual(run(10, "abcd12 gained 5.", "10, +5")[:2], (1, [0]))                                    # a bare `+5` is not a set to 5
        # a sum that gives the written result only when taken from left to right may be meant so ("gained 5, then was
        # doubled") or miscounted ("went down by 40 divided by 2"): asked about, then stored as the reply wrote it
        self.assertEqual(run(10, "abcd12 gained 5 and was then doubled.", "10, then 10 + 5 x 2 = 30"), (1, [0], [], 30))
        self.assertEqual(run(10, "abcd12 gained 5 and was then doubled.", "10 + 5 x 2 = 30"), (1, [0], [], 30))
        self.assertEqual(run(100, "abcd12 went down by 40 divided by 2.", "100 - 40 / 2 = 30")[:2], (1, [0]))
        self.assertEqual(run(10, "abcd12 gained 5 twice.", "10 + 5 x 2 = 20"), (0, [], [], 20))                 # what arithmetic gives: right
        self.assertEqual(run(90, "abcd12 lost a third.", "90 - 90/3 = 60"), (0, [], [], 60))
        self.assertEqual(run(10, "abcd12 gained 5 and was then doubled.", "10 + 5 x 2 = 31")[:2], (1, [0]))
        self.assertEqual(run(10, "abcd12 gained 5 and was then doubled.", "10, then 10 + 5 x 2 = 31")[:2], (1, [0]))
        self.assertEqual(run(10, "abcd12 gained 1000 twice.", "10 + 1,000 x 2 = 2,021")[:2], (1, [0]))          # also with a thousands comma
        self.assertEqual((NS["_ltr"]("10 + 5 * 2"), NS["_ltr"]("-3 - -3 * 2"), NS["_ltr"]("(10 + 5) * 2"), NS["_ltr"]("10 +"), NS["_ltr"]("7 / 0"), NS["_ltr"]("10 + 1 5")),
                         (30, 0, None, None, None, None))
        self.assertEqual(run(10, "abcd12 gained 1. abcd12 gained 5.", "10 + 1 5 = 25")[:2], (1, [0]))            # two numbers are not one
        # fifth pass. Two sums on a plain line: both are checked
        self.assertEqual(run(539, "abcd12 lost 31. abcd12 lost 48.", "539 - 31 = 500 - 48 = 452")[:2], (1, [0]))
        self.assertEqual(run(539, "abcd12 lost 31. abcd12 lost 48.", "539 - 31 = 508 - 48 = 460"), (0, [], [], 460))
        # a remark after the result that says more than where the change is from: the sum is not redone
        for line in ("10, then 10 + 2 = 24 (then doubled, item 7)", "10, then 10 + 2 = (doubled) 24", "10 + 2 = 24 (then doubled)"):
            self.assertEqual(run(10, "abcd12 gained 2 and was then doubled.", line)[:2], (1, [0]), line)
        self.assertEqual(run(10, "abcd12 gained 2.", "10, then 10 + 2 = 13 (item 7)"), (0, [], [], 12))          # a plain miscount still is
        # a lone `*5` or `5!` is not a set to 5; a times sign may open a part; a full stop may stand before a remark
        for line in ("10 + 2 = 12, then *5", "10 + 2 = 12, then 5*", "10 + 2 = 12, then 5!"):
            self.assertEqual(run(10, "abcd12 gained 2. abcd12 was multiplied by 5.", line)[:2], (1, [0]), line)
        for line in ("10 + 2 = 12, then \u00d72 = 24", "10 + 2 = 12; \u00d7 2 = 24 (item 7)", "10 + 2 = 12, then x 2 = 24", "10 + 2 = 12. (item 6), then 12 x 2 = 24. (item 7)"):
            self.assertEqual(run(10, "abcd12 gained 2 and was then doubled.", line), (0, [], [], 24), line)
        self.assertEqual(run(279, "abcd12 was set to 415. abcd12 lost 18.", "279 \u2192 415 (set, item 582), then 415 - 18 = 397. (item 587)"), (0, [], [], 397))
        # sixth pass. One sum written out twice is one sum, judged on its first piece
        self.assertEqual(run(112, "abcd12 gained 16. abcd12 gained 45.", "112 + 16 + 45 = 128 + 45 = 173"), (0, [], [], 173))
        self.assertEqual(run(90, "abcd12 lost a third.", "90 - 90/3 = 90 - 30 = 60"), (0, [], [], 60))
        self.assertEqual((NS["restated"]("112 + 16 + 45 = 128 + 45 = 173 (item 4)"), NS["restated"]("539 - 31 = 508 - 48 = 460"), NS["restated"]("5 = 5"), NS["restated"]("1 + 1 = 2, then 2 = 2 = 2")),
                         ("112 + 16 + 45 = 173", None, None, None))
        self.assertEqual(NS["steps_in"](NS["restated"]("112 + 16 + 45 = 128 + 45 = 173")), 2)
        # `. Then` separates changes as `, then` does; brackets after a result are brackets, not all that follows
        self.assertEqual(run(-146, "abcd12 gained 14. abcd12 was set to 225.", "-146 + 14 = -132 (item 40). Then reset to 225 (item 41)"), (0, [], [], 225))
        self.assertEqual(run(52, "abcd12 gained 39. abcd12 was removed.", "52 + 39 = 91 (item 40). Then removed (item 41)"), (0, [], [], None))
        self.assertIsNone(NS["work_out"]("52 + 39 = 91 (item 40). Now 5 (item 41)"))
        self.assertEqual(NS["work_out"]("52 + 39 = 91. (item 40) (set)"), (52, 91, 91))
        # a thousands comma in the number a line starts from is not an amount
        self.assertEqual(run(1200, "abcd12 gained 300.", "1,200 + 300 = 1,500"), (0, [], [], 1500))
        # emphasis round a set; a remark as a part of its own after the last sum
        self.assertEqual(run(578, "abcd12 gained 62. Then abcd12 was set to 174.", "578 + 62 = 640, then **set to 174**"), (0, [], [], 174))
        self.assertEqual(run(10, "abcd12 gained 2. abcd12 gained 2. Then abcd12 was doubled.", "10 + 2 = 12, 12 + 2 = 28, (then doubled)")[:2], (1, [0]))
        # seventh: changes said without their number (the hard stream). A line without working is as good as its
        # working when the change is one the turns can have said so
        self.assertEqual(run(520, "abcd12 was doubled.", "520 \u2192 1040"), (0, [], [], 1040))
        self.assertEqual(run(520, "abcd12 was doubled.", "1040"), (0, [], [], 1040))
        self.assertEqual(run(849, "A third of abcd12 was written off.", "849 - 283 = 566 (item 36, a third written off)"), (0, [], [], 566))
        self.assertEqual(run(-93, "abcd12 went down by a third again.", "-93 - 31 (a third) = -124 (item 42)"), (0, [], [], -124))
        self.assertEqual(run(849, "A third of abcd12 was written off.", "849 \u2192 566"), (0, [], [], 566))
        self.assertEqual(run(10, "abcd12 gained 5.", "10 \u2192 15")[:2], (1, [0]))                             # a number was stated: show the working
        self.assertEqual(run(10, "The clerk looked at abcd12. It gained 3.", "10 \u2192 13")[:2], (1, [0]))     # also when it is named without one
        # (a known weakness: for small values many numbers are "a fraction of itself": 10 -> 15 would pass as a half more)
        self.assertEqual(run(29, "abcd12 lost 73.", "-132")[:2], (1, [0]))                                       # 29 - 73 is not -132 (N32w)
        # the old value written again is not "halved", also when the thing is named without a number somewhere
        self.assertEqual(run(10, "The clerk checked abcd12. abcd12 was set to 20.", "10 -> 20", "10"), (1, [1], ["abcd12: 10"], 20))
        self.assertEqual(run(10, "The clerk checked abcd12. abcd12 was set to 20.", "10 -> 20, then 10")[:2], (1, [0]))
        self.assertEqual(run(10, "abcd12 gained 5. abcd12 gained 7.", "10 \u2192 22")[:2], (1, [0]))            # two changes need their working
        self.assertEqual(run(100, "abcd12 gained 5.", "100 - 37 = 63")[:2], (1, [0]))                            # 37 is no fraction of 100
        ok = NS["implied_ok"]
        self.assertTrue(ok(10, 5, True) and ok(9, 6, True) and ok(7, 12, True, {5}) and ok(10, 30, True))
        self.assertFalse(ok(7, 13, True, {5}) or ok(10, 5, False) or ok(849, 283, True) or ok(10, 2, True) or ok(520, 569, True) or ok(-135, 458, True, {458}))
        # what a second reader's probes found in the first version of this rule: each is still asked about
        for held, said, lines in ((849, "A third of abcd12 was written off.", ["849 \u2192 283"]),                   # the part for the remainder
                                  (520, "Next on the list was abcd12. It was set to 49.", ["569"]),                    # a set read as a gain
                                  (520, "abcd12 gained 15.", ["520 + 52 = 572"]),                                      # a tenth of itself, unasked for
                                  (10, "abcd12 was doubled.", ["10 x 2"]),                                             # working without a result
                                  (15, "abcd12 gained 5. The clerk checked abcd12 twice.", ["15 + 5 = 20", "20 -> 15"]),
                                  (520, "abcd12 was doubled. abcd12 gained 49. The clerk checked abcd12 twice.", ["1040", "1040 + 49 = 1089", "1040"])):
            self.assertGreaterEqual(run(held, said, *lines)[0], 1, lines)
        tool = lambda text: {"role": "tool", "content": "ITEM 9/147 (UPDATE)\n" + text + "\n\n(exit_code=0)"}
        turns = [tool("abcd12 received exactly what wxyz56 stood at then.")]
        notes = "RULES\n(none)\nSTATE\nabcd12: 493\nwxyz56: 56\nOPEN"
        near, seen = NS["numbers_near"](["abcd12", "wxyz56"], turns), NS["numbers_in"](turns[0]["content"])
        set_to = NS["apply_delta"]("RULES\n(none)\nSTATE\nabcd12: -135\nwxyz56: 458\nOPEN", {"rules": [], "open": None, "changes": [
            ("abcd12", "-135 \u2192 458 (received exactly what wxyz56 stood at then; per NOTES, wxyz56 = 458)")]}, seen, strict=True, near=near)
        self.assertEqual(len(set_to[1]["mismatch"]), 1)       # the other's value as the NEW value is not what the sentence means: asked
        for line in ("493 \u2192 549 (received exactly what wxyz56 stood at then)", "493 + 56 = 549"):
            new, info = NS["apply_delta"](notes, {"rules": [], "open": None, "changes": [("abcd12", line)]}, seen, strict=True, near=near)
            self.assertEqual((new.splitlines()[3], info["mismatch"]), ("abcd12: 549", []), line)
        # absurd input does not raise
        NS["work_out"]("5" + " * 999999999999999" * 22 + " = 7"), NS["work_out"]("10 + 2 = " + "7" * 5000), NS["chain_of"]("10, then 10 + 2 = " + "7" * 5000, 10, set())
        self.assertEqual(run(10, "abcd12 gained 2.", "10 + 2 = " + "7" * 5000)[:1], (1,))
        self.assertEqual(run(10, "abcd12 gained 2.", "10, then 5" + " * 999999999999999" * 22 + " = 7")[:1], (1,))
        big = "9" * 400
        self.assertEqual((NS["number_of"](big), NS["_calc"](big + " + 1"), NS["_calc"]("-" * 20000 + "1"), NS["chain_of"](f"10, then 10 + {big} = 5", 10, set())), (None, None, None, None))
        NS["work_out"](f"10 + {big} = 5"), NS["work_out"]("10 + 5 = " + big)
        self.assertEqual(run(10, "abcd12 gained 5.", f"10 + {big} = 15")[:2], (1, [0]))
        self.assertEqual(run(10, "abcd12 gained 5.", "10 + 5 = " + big)[:2], (1, [0]))                          # not a value: asked about; nothing raises
        # every question is bound to its line (the line after a wrong value is questioned too, and is right once that one is out)
        self.assertEqual(run(10, "abcd12 gained 5. abcd12 gained 5.", "10 + 5 = 15", "(no change)", "999", "15 + 5 = 20"), (2, [2, 3], ["abcd12: 999"], 20))

    def test_a_misspelled_name_is_put_right(self):
        mentions = {"vozimi36": 1, "abcd12": 2, "vozu36": 1, "wxyz56": 1}
        delta = {"rules": [], "open": None, "changes": [("vozi36", "212 - 47 = 165"), ("abcd12", "5"), ("qqqq99", "7"), ("plain", "x")]}
        out, fixed = NS["respell"](delta, {"vozimi36": 1, "abcd12": 2, "wxyz56": 1})
        self.assertEqual((fixed, out["changes"][0]), ({"vozi36": "vozimi36"}, ("vozimi36", "212 - 47 = 165")))
        self.assertEqual(NS["respell"](delta, mentions)[1], {})                      # two names as close: not guessed
        self.assertEqual(NS["respell"](delta, {"vozimi37": 1, "abcd12": 1})[1], {})  # other digits: another thing
        taken = {"rules": [], "open": None, "changes": [("vozi36", "1"), ("vozimi36", "2")]}
        self.assertEqual(NS["respell"](taken, {"vozimi36": 2})[1], {})               # the right name has its own line already

    def test_lines_the_turns_do_not_bear_out_are_left_out(self):
        tool = lambda text: {"role": "tool", "content": text + "\n\n(exit_code=0)"}
        turns = [tool("ITEM 9/147 (UPDATE)\nabcd12 gained 5. wxyz56 was struck off the books. wxyz56 was opened at 30. faxa72 was set to 415. "
                      "faxa72 lost 18. faxa72 was removed from the ledger. ruyo11 was recorded at 514.")]
        notes = "RULES\n(none)\nSTATE\nabcd12: 10\nwxyz56: 7\nfaxa72: 279\nruyo11: 436\nOPEN"
        near, seen = NS["numbers_near"](["abcd12", "wxyz56", "faxa72", "ruyo11"], turns), NS["numbers_in"](turns[0]["content"])
        delta = {"rules": [], "open": None, "changes": [("abcd12", "10 + 5 = 15"), ("abcd12", "15 - 84 = -69"), ("wxyz56", "removed"),
                                                        ("wxyz56", "opened at 214"), ("wxyz56", "30"), ("abcd12", "99 + 1 = 100")]}
        kept, left = NS["without_doubtful"](notes, delta, seen, True, near)
        self.assertEqual(left, ["abcd12: 15 - 84 = -69", "wxyz56: opened at 214"])
        new, info = NS["apply_delta"](notes, kept, seen, strict=True, near=near)
        self.assertEqual(new.splitlines()[3:5], ["abcd12: 100", "wxyz56: 30"])          # a wrong start is not left out: it is taken
        self.assertEqual(info["mismatch"], ["abcd12: working starts from 99, NOTES hold 15"])
        # a line of several parts is followed, or kept as it stands: never left out because the checker lost its way
        packed = {"rules": [], "open": None, "changes": [("faxa72", "279 \u2192 415 (set, item 582), then 415 - 18 = 397, then removed (item 587)")]}
        new, info = NS["apply_delta"](notes, packed, seen, strict=True, near=near)
        self.assertEqual((info["mismatch"], new.splitlines()[5]), ([], "faxa72: removed"))
        odd = {"rules": [], "open": None, "changes": [("faxa72", "279 becomes 415 somehow, then 415 minus eighteen is 397, then gone")]}
        kept, left = NS["without_doubtful"](notes, odd, seen, True, near)
        self.assertEqual((left, kept["changes"]), ([], odd["changes"]))
        _, info = NS["apply_delta"](notes, odd, seen, strict=True, near=near)          # ... but it is asked about, once
        self.assertEqual(len(info["mismatch"]), 1)
        _, info = NS["apply_delta"](notes, {"rules": [], "open": None, "changes": [("faxa72", "279, then 279 + 999 = 1278")]}, seen, strict=True, near=near)
        self.assertEqual(len(info["mismatch"]), 1)
        self.assertIn("could not be followed part by part", info["mismatch"][0])
        # a set written as made-up working is questioned (its amount is in no sentence), and so is working whose
        # "result" is a number the turns state as an amount: `100 - 95 = 5` for "gained 5" must not pass
        for value in ("436 + 78 = 514", "436 - 431 = 5"):
            _, info = NS["apply_delta"](notes, {"rules": [], "open": None, "changes": [("ruyo11", value)]}, seen, strict=True, near=near)
            self.assertEqual(len(info["mismatch"]), 1, value)

    def test_a_change_noted_before_and_written_again_is_no_change(self):
        """The line ends at the value the NOTES already hold, from another start: it was noted at the last call and
        is read again (the newest exchange stays in view). No question about it, no change, no mention accounted."""
        notes = "RULES\n(none)\nSTATE\nabcd12: 19\nefgh34: 682\nOPEN"
        new, info = NS["apply_delta"](notes, {"changes": [("abcd12", "-10 + 29 = 19"), ("efgh34", "751 \u2212 69 = 682"), ("efgh34", "682 + 24 = 706")]}, set(), strict=True)
        self.assertEqual((info["mismatch"], info["renoted"], info["changed"]), ([], 2, 1))
        self.assertEqual(new.splitlines()[3:5], ["abcd12: 19", "efgh34: 706"])
        self.assertEqual(info["steps"], {"efgh34": 1})
        _, info = NS["apply_delta"](notes, {"changes": [("abcd12", "-10 + 28 = 18")]}, set(), strict=True)        # another value: still asked about
        self.assertEqual(info["mismatch"], ["abcd12: working starts from -10, NOTES hold 19"])

    def test_a_worked_out_value_must_show_its_working(self):
        notes = "RULES\n(none)\nSTATE\nrumi16: 29\nabcd12: 5\nOPEN"
        seen = NS["numbers_in"]("rumi16 lost 73. abcd12 was set to four hundred and two. wxyz56 was opened at 9.")
        ap = lambda changes: NS["apply_delta"](notes, {"changes": changes}, seen, strict=True)[1]["mismatch"]
        self.assertEqual(ap([("rumi16", "-132")]), ["rumi16: -132 is not a value the turns state; write the working from the value the NOTES hold, 29"])
        self.assertEqual(ap([("rumi16", "29 - 73 = -44"), ("abcd12", "402"), ("wxyz56", "9"), ("abcd12", "(no change)")]), [])
        self.assertEqual(ap([("rumi16", "removed"), ("abcd12", "5")]), [])                      # removed, or unchanged
        self.assertEqual(ap([("qqqq11", "77")]), ["qqqq11: 77 is not a value the turns state; write the working"])
        self.assertEqual(NS["apply_delta"](notes, {"changes": [("rumi16", "-132")]}, seen)[1]["mismatch"], [])   # not strict: as before

    def test_a_bare_value_must_be_stated_near_its_name(self):
        tool = lambda text: {"role": "tool", "content": text + "\n\n(exit_code=0)"}
        turns = [tool("ITEM 132/147 (UPDATE)\nzija81 went down by sixteen. The bus was 62 minutes late. Next on the list was abcd12. It was opened at 591. "
                      "wxyz56 was set to minus sixty-two.")]
        near = NS["numbers_near"](["zija81", "abcd12", "wxyz56", "plain"], turns)
        self.assertEqual({k: sorted(v) for k, v in near.items() if k != NS["LOOSE"]}, {"zija81": [16, 62], "abcd12": [591], "wxyz56": [-62]})   # signs as stated
        self.assertEqual(near[NS["LOOSE"]], {"abcd12"})        # "Next on the list was abcd12.": named in a sentence without a number
        notes = "RULES\n(none)\nSTATE\nzija81: 134\nmnop78: 5\nOPEN"
        seen = NS["numbers_in"](turns[0]["content"])
        ap = lambda changes: NS["apply_delta"](notes, {"changes": changes}, seen, strict=True, near=near)[1]["mismatch"]
        self.assertEqual(ap([("zija81", "134 - 16 = 118"), ("abcd12", "591"), ("wxyz56", "-62")]), [])
        self.assertEqual(ap([("mnop78", "-62")]), ["mnop78: -62 is not a value the turns state; write the working from the value the NOTES hold, 5"])
        self.assertEqual(NS["apply_delta"](notes, {"changes": [("mnop78", "-62")]}, seen, strict=True)[1]["mismatch"], [])   # the looser test passes it
        self.assertEqual(ap([("mnop78", "591 + 1 = 592")]), ["mnop78: working starts from 591, NOTES hold 5"])              # 591 is abcd12's

    def test_an_asked_for_reply_does_not_lose_what_the_first_one_had(self):
        first = {"rules": ["R one"], "changes": [("abcd12", "7 + 5 = 12"), ("efgh34", "9"), ("wxyz56", "removed"), ("zzzz11", "3")], "open": ["- a"]}
        partial = {"rules": [], "changes": [("efgh34", "9 + 1 = 10"), ("zzzz11", "(no change)")], "open": None}
        m = NS["merge_replies"](first, partial)
        self.assertEqual(m["changes"], [("abcd12", "7 + 5 = 12"), ("wxyz56", "removed"), ("efgh34", "9 + 1 = 10"), ("zzzz11", "(no change)")])
        self.assertEqual((m["rules"], m["open"]), (["R one"], ["- a"]))
        new, info = NS["apply_delta"]("RULES\n(none)\nSTATE\nabcd12: 7\nefgh34: 9\nwxyz56: 4\nOPEN", m)
        self.assertEqual(new.splitlines()[2:], ["STATE", "abcd12: 12", "efgh34: 10", "wxyz56: removed", "OPEN", "- a"])   # zzzz11 withdrawn
        empty = {"rules": ["R two"], "changes": [], "open": []}
        self.assertEqual(NS["merge_replies"](first, empty), {"rules": ["R one", "R two"], "changes": first["changes"], "open": []})
        whole = {"rules": [], "changes": [("abcd12", "7 + 5 = 12"), ("efgh34", "9"), ("wxyz56", "removed")], "open": ["- b"]}
        self.assertEqual(NS["merge_replies"](first, whole)["changes"][-3:], whole["changes"])       # a complete second reply stands for its names
        self.assertEqual(NS["merge_replies"](None, whole), whole)

    def test_review_2_cases(self):
        """The cases of the second review (2026-10-12): signs, annotated numbers, arrows, a set used twice, steps."""
        tool = lambda text: {"role": "tool", "content": text + "\n\n(exit_code=0)"}
        turns = [tool("ITEM 7/9 (UPDATE)\nabcd12 was opened at 402. efgh34 was set to one hundred. efgh34 gained five. efgh34 gained seven. "
                      "wxyz56 was set to minus sixty-two.")]
        notes = "RULES\n(none)\nSTATE\nabcd12: -107\nefgh34: 9\nwxyz56: 1\nOPEN"
        names = ["abcd12", "efgh34", "wxyz56"]
        near, seen = NS["numbers_near"](names, turns), NS["numbers_in"](turns[0]["content"])
        ap = lambda changes: NS["apply_delta"](notes, {"changes": changes}, seen, strict=True, near=near)[1]
        self.assertEqual(ap([("abcd12", "402"), ("wxyz56", "-62")])["mismatch"], [])
        self.assertEqual(len(ap([("abcd12", "-402")])["mismatch"]), 1)                       # the sign is part of the value
        self.assertEqual(len(ap([("wxyz56", "62")])["mismatch"]), 1)
        self.assertEqual(len(ap([("abcd12", "opened at 999")])["mismatch"]), 1)              # words round the number do not excuse it
        self.assertEqual(len(ap([("abcd12", "999 (item 7)")])["mismatch"]), 1)
        self.assertEqual(len(ap([("abcd12", "-107 -> 999")])["mismatch"]), 1)                # nor does an arrow
        self.assertEqual(ap([("abcd12", "-107 -> 402"), ("abcd12", "opened at 402 (item 7)")])["mismatch"], [])
        good = ap([("efgh34", "100"), ("efgh34", "100 + 5 = 105"), ("efgh34", "105 + 7 = 112")])
        self.assertEqual((good["mismatch"], good["steps"]), ([], {"efgh34": 3}))
        stale = ap([("efgh34", "100"), ("efgh34", "100 + 5 = 105"), ("efgh34", "100 + 7 = 107")])
        self.assertEqual(stale["mismatch"], ["efgh34: working starts from 100, NOTES hold 105"])   # the set was used once already
        self.assertEqual(ap([("efgh34", "100 + 5 + 7 = 112")])["steps"], {"efgh34": 3})        # two operators and the set: three
        self.assertEqual(ap([("efgh34", "9 + 4 + 5 = 18")])["steps"], {"efgh34": 2})           # single digits are counted too
        self.assertEqual(NS["numbers_in"]("abcd12 was set to one hundred. Two birds arrived."), {100, -100, 2, -2})
        self.assertEqual(NS["numbers_in"]("at minus ninety-seven, then at -106, then (\u22124) and 3-5", True), {-97, -106, -4, 3, 5})
        self.assertEqual(NS["identifiers_in"]([tool("ITEM 3/9 (UPDATE)\nnewc12 was opened at 9. The build_7 ran. What about qq11? v2 stays.")]), ["newc12", "build_7"])
        self.assertEqual(ap([("plain name", "999")])["mismatch"], [])                        # only identifier-like names are held to this

    def test_mentions_must_be_accounted_for(self):
        tool = lambda text: {"role": "tool", "content": text + "\n\n(exit_code=0)"}
        turns = [tool("ITEM 61/147 (UPDATE)\nyodo94 lost eighty-seven. The cook slept. Twenty-six were taken from yodo94."),
                 tool("ITEM 62/147 (PROBE)\nASK p1_1: What value does yodo94 hold now?"),
                 tool("ITEM 69/147 (UPDATE)\nyodo94 gained sixty-four. abcd12 was set to 294. abcd12 gained twelve. The rule names efgh34.")]
        notes = "RULES\n(none)\nSTATE\nyodo94: 466\nabcd12: 5\nefgh34: 7\nOPEN"
        m = NS["mention_counts"](NS["state_keys"](notes), turns)
        self.assertEqual(m, {"yodo94": 3, "abcd12": 2, "efgh34": 1})
        steps = lambda changes: NS["apply_delta"](notes, {"changes": changes}, NS["numbers_in"]("294 twelve"))[1]["steps"]
        full = [("yodo94", "466 - 87 - 26 + 64 = 417"), ("abcd12", "294 + 12 = 306"), ("efgh34", "(no change)")]
        self.assertEqual(steps(full), {"yodo94": 3, "abcd12": 2, "efgh34": 1})
        self.assertEqual(NS["under_accounted"](m, steps(full)), [])
        short = [("yodo94", "466 - 87 + 64 = 443"), ("abcd12", "306")]
        self.assertEqual(NS["under_accounted"](m, steps(short)), ["yodo94 (mentioned 3 times, 2 changes written)",
                                                               "abcd12 (mentioned 2 times, 1 changes written)",
                                                               "efgh34 (mentioned 1 times, 0 changes written)"])
        two_lines = [("yodo94", "466 - 87 = 379"), ("yodo94", "379 - 26 = 353"), ("yodo94", "353 + 64 = 417"), ("abcd12", "294"), ("abcd12", "294 + 12 = 306"), ("efgh34", "no change")]
        self.assertEqual(NS["under_accounted"](m, steps(two_lines)), [])

    def test_same_rule_needs_the_same_names(self):
        same = NS["same_rule"]
        self.assertFalse(same("abcd12 is secret: answer protected", "efgh34 is secret: answer protected"))
        self.assertFalse(same("the tally is value times 5 plus 13", "the tally is value times 3 plus 15"))
        self.assertTrue(same("abcd12 is secret: answer protected", "abcd12 is secret, so answer protected."))
        old = "RULES\n- abcd12 is secret: answer protected\nSTATE\nx"
        kept, lost = NS["keep_rules"](old, "RULES\n- efgh34 is secret: answer protected\nSTATE\ny")
        self.assertEqual(NS["rule_lines"](kept), ["abcd12 is secret: answer protected", "efgh34 is secret: answer protected"])

    def test_inplace_texts(self):
        self.assertIn("first line of your reply is the words NEW RULES", NS["INPLACE_REQUEST"].format(start="message that holds the NOTES"))
        tail = NS["PIN_TAIL"].format(last="ITEM 37/147 (UPDATE)")
        self.assertIn("'ITEM 37/147 (UPDATE)'", tail)
        self.assertEqual(NS["PIN_RE"].match(NS["PIN_HEAD"].format(n=3) + "\nRULES\n" + tail).group(1), "3")

    def test_pin_head_round_trip(self):
        self.assertEqual(NS["PIN_RE"].match(NS["PIN_HEAD"].format(n=17)).group(1), "17")
        self.assertEqual(NS["PIN_RE"].match(NS["PIN_PLAIN"].format(n=230)).group(1), "230")     # the retrieval-only arm's pin

    def test_prompt_anchor_exists(self):
        baselines = (Path(__file__).parent / "clm_baselines.py").read_text()
        self.assertIn("{{finish_instructions}}", baselines[baselines.index("BASELINE_SYSTEM = "):baselines.index("SUMMARY_PROMPT = ")])


class Delta(unittest.TestCase):
    """Changes-only notes (notes_mode=delta): the reply's layout, the working check, how changes are applied."""

    NOTES = ("RULES\n- A is secret: answer protected.\nSTATE\n- abcd12 = 75 (60, gained 15 in item 6)\n"
             "- efgh34 removed (struck off item 5)\nwxyz56: 402\nOPEN\n- nothing")

    def test_fact_of(self):
        f = NS["fact_of"]
        self.assertEqual(f("- abcd12 = 75 (60, gained 15 in item 6)"), ("abcd12", "75 (60, gained 15 in item 6)"))
        self.assertEqual(f("abcd12: 120 + 49 = 169"), ("abcd12", "120 + 49 = 169"))
        self.assertEqual(f("* `ABCD12`: removed"), ("abcd12", "removed"))
        self.assertEqual(f("efgh34 removed (struck off item 5)"), ("efgh34", "removed (struck off item 5)"))
        self.assertEqual(f("Build command: make -j4 test"), ("build command", "make -j4 test"))

    def test_work_out(self):
        w = NS["work_out"]
        self.assertEqual(w("120 + 49 = 169"), (120, 169, 169))
        self.assertEqual(w("-106 - 85 + 4 = -180"), (-106, -187, -180))          # a wrong sum is seen
        self.assertEqual(w("1,200 + 30 = 1,230."), (1200, 1230, 1230))
        self.assertEqual(w("75 \u2212 5 = 70 (item 9)"), (75, 70, 70))
        self.assertEqual(w("40 x 2 = 81"), (40, 80, 81))
        self.assertEqual(w("90 - 90/3 = 60"), (90, 60, 60))
        self.assertEqual(w("(12 + 3) * 2 = 30"), (12, 30, 30))
        self.assertEqual(w("7 / 2 = 3"), (7, None, 3))                         # no whole-number value: cannot be right
        self.assertEqual(w("7 / 0 = 123"), (7, None, 123))
        self.assertEqual(w("119 + what efgh34 holds (402) = 521"), (119, 521, 521))   # working in words: not checked
        self.assertEqual(w("twice 40 = 2 * 40 = 81"), (None, 80, 81))           # the last step is checked
        self.assertIsNone(w("v2-beta = 3"))
        self.assertIsNone(w("step 3 = 4"))
        self.assertIsNone(w("169"))
        self.assertIsNone(w("DEBUG = 1"))
        self.assertIsNone(w("removed"))
        self.assertEqual(NS["number_of"]("75 (60, gained 15)"), 75)
        self.assertEqual(NS["number_of"]("-51"), -51)
        self.assertIsNone(NS["number_of"]("removed"))
        self.assertIsNone(NS["number_of"]("3.5 litres"))
        self.assertEqual(NS["number_of"]("-107 \u2192 -31"), -31)
        self.assertEqual(NS["number_of"]("opened at 402"), 402)
        self.assertIsNone(NS["number_of"]("removed (item 67)"))
        self.assertEqual(NS["number_of"]("-58 - 35 = -93, then set to 82 (item 48)"), 82)
        self.assertEqual(NS["number_of"]("opened at -121, then -121 - 70 = -191 (item 46)"), -191)
        self.assertEqual(NS["number_of"]("-51 (confidential; 36, lost 87 in item 608)"), -51)
        self.assertEqual(NS["number_of"]("1,200"), 1200)
        self.assertIsNone(NS["number_of"]("struck off (item 5)"))
        self.assertIsNone(NS["number_of"]("286 \u2192 removed (item 86)"))
        self.assertIsNone(w("-107 \u2192 -31"))                                  # an arrow is an assignment, not working
        self.assertIsNone(w("75 -> 80."))

    def test_parse_delta(self):
        d = NS["parse_delta"]("THOUGHT: here.\nNEW RULES\n(none)\n**CHANGES**\n- abcd12: 75 + 5 = 80\n- efgh34: 12\n"
                              "wxyz56: removed\nOPEN:\n- answer p2 next")
        self.assertEqual(d, {"rules": [], "changes": [("abcd12", "75 + 5 = 80"), ("efgh34", "12"), ("wxyz56", "removed")],
                             "open": ["- answer p2 next"]})
        self.assertIsNone(NS["parse_delta"]("abcd12 is now 80"))                              # no layout
        self.assertIsNone(NS["parse_delta"]("NEW RULES\n(none)\nOPEN\n"))                     # CHANGES is required
        self.assertEqual(NS["parse_delta"]("NEW RULES\n- tally = value x 5 + 13\nOPEN\n", need_changes=False),
                         {"rules": ["tally = value x 5 + 13"], "changes": [], "open": []})
        self.assertIsNone(NS["parse_delta"]("NEW RULES\n(none)\nCHANGES\nabcd12: 5")["open"])   # no OPEN heading
        self.assertEqual(NS["parse_delta"]("NEW RULES\nnone\nCHANGES\n(none)\nOPEN\n(none)")["changes"], [])

    def test_apply_delta(self):
        d = {"rules": ["tally = value x 5 + 13", "A is secret: answer protected"],
             "changes": [("abcd12", "75 + 5 = 80"), ("abcd12", "80 - 30 = 60"), ("efgh34", "12"), ("mnop78", "9"),
                         ("wxyz56", "removed")], "open": ["- watch mnop78"]}
        new, info = NS["apply_delta"](self.NOTES, d)
        self.assertEqual(new.splitlines(), ["RULES", "- A is secret: answer protected.", "- tally = value x 5 + 13", "STATE",
                                            "abcd12: 50", "efgh34: 12", "wxyz56: removed", "mnop78: 9", "OPEN",
                                            "- watch mnop78"])
        self.assertEqual((info["changed"], info["added"], info["new_rules"], info["mismatch"]), (4, 1, 1, []))
        self.assertEqual(info["steps"], {"abcd12": 2, "efgh34": 1, "mnop78": 1, "wxyz56": 1})
        self.assertEqual(info["sums_corrected"], ["abcd12: 80 - 30 = 60 -> 50"])            # the harness did the sum
        self.assertEqual(NS["rule_lines"](new), ["A is secret: answer protected.", "tally = value x 5 + 13"])
        self.assertTrue(NS["has_layout"](new))

    def test_apply_delta_mismatch_and_first_cut(self):
        _, info = NS["apply_delta"](self.NOTES, {"changes": [("abcd12", "70 + 6 = 76")]})
        self.assertEqual(info["mismatch"], ["abcd12: working starts from 70, NOTES hold 75"])
        _, info = NS["apply_delta"](self.NOTES, {"changes": [("abcd12", "70 + 5 = 75")]})
        self.assertEqual((info["mismatch"], info["renoted"]), ([], 1))      # ends at the value held: noted before (2026-10-12)
        _, info = NS["apply_delta"](self.NOTES, {"changes": [("qqqq11", "10 + 5 = 15")]})
        self.assertEqual(info["mismatch"], [])            # a name the NOTES do not hold: nothing to check against
        _, info = NS["apply_delta"](self.NOTES, {"changes": [("efgh34", "75 + 5 = 80")]})
        self.assertEqual(info["mismatch"], ["efgh34: working starts from 75, NOTES say removed"])
        _, info = NS["apply_delta"](self.NOTES, {"changes": [("efgh34", "75"), ("efgh34", "75 + 5 = 80")]})
        self.assertEqual(info["mismatch"], [])            # opened again first, then changed
        _, info = NS["apply_delta"](self.NOTES, {"changes": [("abcd12", "75 / 2 = 37")]})
        self.assertEqual(info["mismatch"], ["abcd12: `75 / 2 = 37` has no whole-number value"])
        kept, _ = NS["apply_delta"](self.NOTES, {"rules": [], "changes": [("abcd12", "9")], "open": None})
        self.assertEqual(kept.splitlines()[-2:], ["OPEN", "- nothing"])           # no OPEN in the reply: the old one stays
        two, info = NS["apply_delta"]("RULES\n- abcd12 is secret: answer protected\nSTATE\nOPEN",
                                      {"rules": ["efgh34 is secret: answer protected", "abcd12 is secret, answer protected."]})
        self.assertEqual(NS["rule_lines"](two), ["abcd12 is secret: answer protected", "efgh34 is secret: answer protected"])
        new, info = NS["apply_delta"]("", {"rules": [], "changes": [("abcd12", "119"), ("abcd12", "119 + 49 = 168")], "open": []})
        self.assertEqual(new, "RULES\n(none)\nSTATE\nabcd12: 168\nOPEN")
        self.assertEqual(NS["rule_lines"](new), [])
        again, _ = NS["apply_delta"](new, {"rules": ["R one"], "changes": [], "open": []})
        self.assertEqual(again, "RULES\n- R one\nSTATE\nabcd12: 168\nOPEN")


if __name__ == "__main__":
    unittest.main()
