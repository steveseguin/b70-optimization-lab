codex
Found 11 defects, most severe first. Paths below are under `experiments/qwen38-27b-b70/scripts/context`; line numbers reflect the latest files read.

1. **P1 — Retrieval can still end the run by overflowing context.** [clm_keeper.py:580](/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts/context/clm_keeper.py:580), also line 785.
   `room // 3` is not the budget’s token count; cutting measures the old NOTES, and the later recital is unreserved. For example, 18K retained tokens + 3K NOTES growth + 10K retrieval + 1K recital exceeds the 30,720 strict target. Oversized reservations can also make `target` negative, removing every removable turn without ensuring a fit. **Smallest fix:** count the final assembled messages, trim retrieval to actual remaining tokens, and reserve NOTES growth and recital space when choosing the cut.

2. **P1 — Sentence isolation handicaps R32 on standing rules.** [rag_retrieve.py:59](/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts/context/rag_retrieve.py:59).
   The generated rule names confidential counters in one sentence, then specifies “answer … protected” in another. A final `QUERY abcd12` cannot retrieve that second sentence: it contains no matching term. R32 has neither NOTES nor recall to recover it. Pronoun-based changes have the same problem. **Smallest fix:** retrieve surrounding sentences or their paragraph, preserving the instruction with its subject.

3. **P1 — Delta mode silently discards distinct rules.** [clm_keeper.py:319](/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts/context/clm_keeper.py:319).
   `same_rule` treats 80% word overlap as equivalence. “abcd12 is secret: answer protected” and “efgh34 is secret: answer protected” share five of six words, so the second rule disappears and never reaches recital. **Smallest fix:** deduplicate only normalized identical rules; retain differing names, numbers and conditions.

4. **P2 — Invalid arithmetic is accepted as a verified value.** [clm_keeper.py:275](/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts/context/clm_keeper.py:275).
   Failed or nonintegral evaluation falls back to the stated result. With NOTES holding 7, `7 / 0 = 123` stores 123; `7 / 2 = 3` stores 3. The working is then erased. **Smallest fix:** distinguish unsupported prose from invalid arithmetic, and send invalid/nonintegral calculations to the full-rewrite fallback.

5. **P2 — Missing or removed starting values bypass the mismatch gate.** [clm_keeper.py:329](/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts/context/clm_keeper.py:329).
   NOTES saying `efgh34 removed` followed by `efgh34: 75 + 5 = 80` resurrects the counter without fallback because `held is None`. Unparseable old values likewise bypass checking. **Smallest fix:** reject unverified arithmetic bases; require an explicit initialization line before arithmetic on a new/reopened counter.

6. **P2 — Missing OPEN is accepted and erases pending work.** [clm_keeper.py:295](/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts/context/clm_keeper.py:295).
   `NEW RULES / CHANGES` without OPEN passes validation and replaces the old OPEN section with nothing. Rules mode even accepts NEW RULES alone. **Smallest fix:** require every mode’s headings in order before applying a delta, allowing the existing retry/fallback machinery to handle omissions.

7. **P2 — Retrieval’s character budget is not enforced.** [rag_retrieve.py:102](/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts/context/rag_retrieve.py:102).
   `size()` excludes “(nothing in the store matches)” and does not measure the exact rendered header. Many unmatched questions can therefore exceed `budget_chars` even after all hits are removed. Budget-pruned matches are also falsely described as nonexistent. **Smallest fix:** budget the actual rendered text, compact empty groups when necessary, and distinguish “omitted for space” from “no matches.”

8. **P2 — Retrieved evidence is silently severed at 300 characters.** [rag_retrieve.py:109](/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts/context/rag_retrieve.py:109).
   A sentence can match a counter or question using text beyond character 300, while the displayed prefix omits that counter, its value or its qualification—even with ample context available. This particularly hurts R32, which cannot request the remainder. **Smallest fix:** retain complete passages within the overall token budget instead of slicing each passage.

9. **P2 — Coverage crashes on supported tasks.** [rag_coverage.py:70](/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts/context/rag_coverage.py:70), also line 74.
   A generated `small` question such as “how many minutes late was the bus” has no counter name, so `m.group(0)` raises. Tasks without standing rules store `"rules": null`, making the later `.get("protected")` raise too. **Smallest fix:** handle small-detail questions explicitly and use `(spec.get("rules") or {})`.

10. **P2 — Procedure coverage ignores the required method.** [rag_coverage.py:67](/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts/context/rag_coverage.py:67).
    The generator emits type `procedure`, but this branch checks `method`. A tally question is consequently marked covered when its counter history is available but its formula is missing. Simply renaming the branch also incorrectly uses `ref_item`—the method’s item—as the current-value horizon. **Smallest fix:** handle `procedure`, requiring the formula plus counter state at the question’s stated horizon.

11. **P2 — Coverage overstates what the live retriever supplies.** [rag_coverage.py:87](/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts/context/rag_coverage.py:87).
    It checks independent, untruncated top-K results, omitting the shared message budget and archived PROBE passages that compete in the live index. A many-question item can therefore report coverage for passages the harness removes. **Smallest fix:** evaluate the same indexed items and budgeted passage selection used by the live retriever, or explicitly label this as an idealized upper bound.

No additional defect found in archive-byte handling, arm wiring, recital ordering, or fallback counter/`self.notes` bookkeeping. The supplied free-format STATE examples work. No additional regression found in default 32K `notes_mode=full`; the newest turn remains protected from cutting.

All **26 targeted unit tests passed**. No files edited; no Docker or GPU jobs run.
