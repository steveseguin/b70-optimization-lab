"""CPU-only checks of rag_retrieve.py (BM25 over archived sentences, the retrieval message of arms R32 / N32r)."""
import unittest

import rag_retrieve as rr

ITEM1 = ("Standing rule: the counters abcd12 and efgh34 are confidential. Answer protected for them.\n\n"
         "The cook fed the yard cat near the canal. abcd12 was opened at fifty-four.")
ITEM2 = "The driver argued about the radio by the east gate. abcd12 went up by four. It rained."
ITEM3 = "The cook argued about the radio by the east gate. wxyz56 was opened at 9."


class Retrieve(unittest.TestCase):
    def index(self, unit="sentence"):
        ix = rr.Index(unit)
        for n, t in ((1, ITEM1), (2, ITEM2), (3, ITEM3)):
            ix.add(n, t)
        return ix

    def test_questions(self):
        text = "PROBE: answer now.\nASK p1_1: What value does abcd12 hold now?\nASK p1_2: In item 2, who argued?\nQUERY wxyz56\nGET abcd12"
        self.assertEqual(rr.questions(text), [("p1_1", "What value does abcd12 hold now?"), ("p1_2", "In item 2, who argued?"),
                                              ("wxyz56", "wxyz56"), ("abcd12", "abcd12")])
        self.assertEqual(rr.questions("The cook fed the cat."), [])

    def test_name_search_finds_every_mention(self):
        hits = self.index().search("What value does abcd12 hold now?", 10)
        self.assertEqual(sorted(n for _, n, p, _ in hits if "abcd12" in p), [1, 1, 2])
        self.assertTrue(all("abcd12" in h[2] for h in hits[:3]))               # the mentions rank first

    def test_item_number_is_searchable(self):
        ix = self.index()
        best = ix.search("In item 3, who argued about the radio by the east gate?", 1)[0]
        self.assertEqual((best[1], best[2]), (3, "The cook argued about the radio by the east gate."))
        best = ix.search("In item 2, who argued about the radio by the east gate?", 1)[0]
        self.assertEqual(best[1], 2)

    def test_add_once_and_units(self):
        ix = self.index()
        n = len(ix.docs)
        self.assertEqual(ix.add(2, ITEM2), 0)
        self.assertEqual(len(ix.docs), n)
        self.assertEqual(len(self.index("paragraph").docs), 4)
        self.assertEqual(rr.Index().search("anything", 5), [])

    def test_note(self):
        ix = self.index()
        note = rr.retrieval_note(ix, "ITEM 4/9 (PROBE)\nASK p1_1: What value does abcd12 hold now?\nASK p1_2: What is zzzz99?", 2)
        lines = note.splitlines()
        self.assertTrue(lines[0].startswith("[[Retrieved for the questions above"))
        self.assertEqual(lines[1], "p1_1:")
        self.assertEqual([ln.split(":")[0] for ln in lines[2:4]], ["item 1", "item 2"])        # in item order
        both = rr.retrieval_note(ix, "ASK p1_1: abcd12", 3).splitlines()[2:]
        self.assertEqual([ln[:22] for ln in both], ["item 1: Standing rule:", "item 1: abcd12 was ope", "item 2: abcd12 went up"])   # reading order inside an item
        self.assertEqual(lines[4], "p1_2: (nothing in the store matches)")
        self.assertEqual(rr.retrieval_note(ix, "ITEM 4/9 (UPDATE)\nNothing asked."), "")
        self.assertEqual(rr.retrieval_note(rr.Index(), "ASK p1_1: What value does abcd12 hold now?"), "")

    def test_sentence_window(self):
        ix = rr.Index()
        ix.add(1, "Attention then turned to abcd12. It went up by four. The cook slept.")
        ix.add(2, "Next on the list was abcd12.")
        note = rr.retrieval_note(ix, "ASK p1_1: What value does abcd12 hold now?", 2, window=1).splitlines()
        self.assertEqual(note[2:], ["item 1: Attention then turned to abcd12. It went up by four.", "item 2: Next on the list was abcd12."])

    def test_note_budget_drops_the_weakest(self):
        ix = self.index()
        text = "ASK p1_1: What value does abcd12 hold now?\nASK p1_2: who argued about the radio by the east gate?"
        full = rr.retrieval_note(ix, text, 5)
        small = rr.retrieval_note(ix, text, 5, budget_chars=len(full) - 150)
        self.assertLess(len(small), len(full))
        self.assertIn("abcd12 went up by four", small)                      # the strongest matches stay
        self.assertIn("p1_2:", small)
        self.assertLessEqual(len(small), len(full) - 150)                  # the rendered text is what is measured
        tiny = rr.retrieval_note(ix, text, 5, budget_chars=len(rr.RETRIEVED_HEAD) + 80)
        self.assertTrue(tiny == "" or "(matches left out for space)" in tiny)
        self.assertNotIn("nothing in the store matches", tiny)
        self.assertEqual(rr.retrieval_note(ix, text, 5, budget_chars=10), "")


if __name__ == "__main__":
    unittest.main()
