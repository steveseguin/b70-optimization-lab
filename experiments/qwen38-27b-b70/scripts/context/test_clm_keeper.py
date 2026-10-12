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
        self.assertEqual({k: sorted(v) for k, v in near.items()}, {"zija81": [16, 62], "abcd12": [591], "wxyz56": [-62]})   # signs as stated
        notes = "RULES\n(none)\nSTATE\nzija81: 134\nmnop78: 5\nOPEN"
        seen = NS["numbers_in"](turns[0]["content"])
        ap = lambda changes: NS["apply_delta"](notes, {"changes": changes}, seen, strict=True, near=near)[1]["mismatch"]
        self.assertEqual(ap([("zija81", "134 - 16 = 118"), ("abcd12", "591"), ("wxyz56", "-62")]), [])
        self.assertEqual(ap([("mnop78", "-62")]), ["mnop78: -62 is not a value the turns state; write the working from the value the NOTES hold, 5"])
        self.assertEqual(NS["apply_delta"](notes, {"changes": [("mnop78", "-62")]}, seen, strict=True)[1]["mismatch"], [])   # the looser test passes it
        self.assertEqual(ap([("mnop78", "591 + 1 = 592")]), ["mnop78: working starts from 591, NOTES hold 5"])              # 591 is abcd12's

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
        _, info = NS["apply_delta"](self.NOTES, {"changes": [("abcd12", "70 + 5 = 75")]})
        self.assertEqual(info["mismatch"], ["abcd12: working starts from 70, NOTES hold 75"])
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
