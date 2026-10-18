# Packet 122 draft budget + draft-HC candidate: candidate closed (2026-10-18)

Lane B, card 2. Draft budget micros `packet122-micro-B-{1,2}` (11:24, 11:26 UTC) and candidate `packet122-draft-hc-micro-B-1` (11:29–11:30), all exact. Second candidate process pulled. No fault (count 2).

**Fresh draft step (production, current line):** 1,382 µs at context 128, 1,933 µs at 4096 (one complete draft step: MTP layer + prefix head + argmax, 59 submissions). Largest classes in the budget run: `draft.logits` ~445 µs (prefix head), draft QSA attention ~230 µs, QSA query gate ~126 µs, QSA select ~98 µs, expert gate/down ~81/61 µs, `draft.merge.projected` ~60 µs, route ~43 µs.

**Candidate (exact draft-HC fusion):** HC classes 123.9 → 113.1 µs (**0.913×**, gate ≤ 0.8×); whole draft step 1,382 → 1,366 µs at 128 (−1.2%, ≈ 0.1% of a hit). Closed.

Implication: the draft step's own cost is dominated by the prefix head (~0.45 ms; packet 114's 80,128-row prefix is already in bundle 7) and the draft's QSA attention/select (context-dependent).

Evidence: `experiments/own-xpu-runtime/stage2/packet122-draft-hc/evidence/micro-B-1/native/iterations.jsonl`, `stage2/packet122-draft-budget/evidence/micro-B-{1,2}/`.
