"""CPU-only checks of the pure parts of arm N32 (clm_keeper.py): item splitting, turn rendering, permanent RULES.
The agent class needs the harness package and litellm, so the module is not imported; no model or device calls."""
import json
from pathlib import Path
import re
from typing import Any
import unittest

SRC = (Path(__file__).parent / "clm_keeper.py").read_text()
NS: dict = {"json": json, "re": re, "Path": Path, "Any": Any, "base64": __import__("base64"), "__file__": str(Path(__file__).parent / "clm_keeper.py")}
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
        self.assertFalse(w([tool("ITEM 3/9 (UPDATE)\nA quiet day. abcd12 went up by four.")]))
        self.assertTrue(w([tool("ITEM 4/9 (PROBE)\nPROBE: answer these questions now.\nASK p1_1: What value?")]))
        self.assertTrue(w([tool("ITEM 9/9 (QUERY)\nThe auditors ask.\nQUERY abcd12")]))
        self.assertTrue(w([tool("ITEM 3/9 (UPDATE)\ntext"), {"role": "user", "content": "CONTEXT LIMIT reached"}]))
        self.assertTrue(w([tool("bash: nope: command not found", 127)]))
        self.assertFalse(w([tool("ITEM 4/9 (PROBE)\nASK p1_1: x"), {"role": "assistant", "content": "ok"}, tool("written")]))

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

    def test_pin_head_round_trip(self):
        self.assertEqual(NS["PIN_RE"].match(NS["PIN_HEAD"].format(n=17)).group(1), "17")

    def test_prompt_anchor_exists(self):
        baselines = (Path(__file__).parent / "clm_baselines.py").read_text()
        self.assertIn("{{finish_instructions}}", baselines[baselines.index("BASELINE_SYSTEM = "):baselines.index("SUMMARY_PROMPT = ")])


if __name__ == "__main__":
    unittest.main()
