# Why does writing slow down 2-3x at long context? (preregistration, 2026-10-17 02:45 EDT)

## Question

The two-card 27B FP8 server writes about 90 tokens/s on short prompts but 41 at 137K and 26 at 246K (measured
10-05, `2026-10-10-context-16k-baseline.md`). Agent streams spend about two thirds of their time writing
(`2026-10-16-fp8-piece-size-prereg.md`, "Where an agent stream's time goes"). On paper, reading the cache once per
step at 137K costs about 8 ms per card (4.5 GB over 16 layers at ~550 GB/s), but the step gets about 40 ms slower.

Suspect: with MTP5 each step checks 6 tokens. `flash_attn_varlen_func` (vllm-xpu-kernels, "spec-decode fast path")
sends them to the split-K decode kernel as 6 separate one-token decodes, and each one reads the whole cache, so a
step reads the cache 6 times unless the card's L2 cache catches the repeats. It keeps every row exactly equal to
plain one-token decoding, which a rewrite must keep too.

## Run (`scripts/bench-decode-attn.py`, runner `scripts/run-20261017-attn-bench.sh` with `BENCH=bench-decode-attn.py`)

R314 image, card 0 only, Gemma stopped first and restored after. Shapes per card: 12 query heads, 2 key/value heads,
head size 256, FP16 paged cache, pages of 832 and 1,280; contexts 1K, 25K, 50K, 100K, 137K, 200K, 246K. Three arms per
point, median of 21 calls each: `decode1` (one token, as the drafter's layer decodes), `fast` (the 6-token check as
the server runs it), `chunk` (the same 6 tokens with the fast path off, the prompt kernel). Recorded per point:
time, the rate of reading the cache's unique bytes, repeats bitwise equal, and how many of the 6 rows equal a plain
one-token decode at that row's own length.

## Predictions

- `decode1` at 100K+: 300-450 GB/s of unique bytes (split-K fills the card).
- `fast` at 100K+: 3-6x the time of `decode1` (the cache is read 6 times, some of the repeats hit L2).
- `fast` rows equal plain decode: 6/6 at every point; `chunk`: not 6/6.
- `chunk` slower than `fast` at 100K+ (12 work-groups, no key split).
- Per step at 137K, 16 layers x `fast` = 20-40 ms, most of the measured slowdown.

## Decision rule

- If `fast` at 100K+ takes 3x `decode1` or more and 16 x `fast` at 137K is 20 ms or more: the lever is a verify
  kernel that reads each key tile once for all 6 rows, with each row's arithmetic unchanged (rows must still equal
  plain decode, 6/6). Next: size the change in the decode kernel source, build it stand-alone, time it with this
  script.
- If `fast` is under 2x `decode1` (L2 already catches the repeats): the lever is the decode kernel's own rate. If
  `decode1` is under 60 % of the card's 608 GB/s, look at its split count. Otherwise the writing-attention lever
  closes, and the slowdown is looked for elsewhere (the drafter, acceptance at long context).

## Result (02:28 EDT, card 0, kernel log clean; `data/2026-10-17-decode-attn/attn-r314.json`)

Median of 21 calls; GB/s = the cache's unique bytes over the call's time; "x" = fast / decode1:

| Page | Context | decode1 ms | GB/s | fast (6 rows) ms | GB/s | x | chunk ms | rows = plain decode (fast / chunk) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 832 | 1K | 0.064 | 32 | 0.110 | 19 | 1.7 | 0.175 | 6 / 0 |
| 832 | 25K | 0.152 | 337 | 0.309 | 166 | 2.0 | 2.72 | 6 / 0 |
| 832 | 50K | 0.235 | 436 | 0.434 | 236 | 1.8 | 5.39 | 6 / 0 |
| 832 | 100K | 0.407 | 503 | 0.737 | 278 | 1.8 | 10.7 | 6 / 0 |
| 832 | 137K | 0.541 | 518 | 0.998 | 281 | 1.8 | 14.7 | 6 / 0 |
| 832 | 200K | 0.764 | 536 | 1.406 | 291 | 1.8 | 21.5 | 6 / 0 |
| 832 | 246K | 0.926 | 544 | 1.837 | 274 | 2.0 | 26.4 | 6 / 0 |

Pages of 1,280 give the same within 4 % (JSON). No missing kernel; every repeat bitwise equal.

- Predictions: `decode1` beat the range (500-544 GB/s at 100K+, 83-89 % of 608). `fast` is 1.8-2.0x `decode1`, under the
  predicted 3-6x: the card's L2 catches most of the five repeat reads. Rows equal plain decode 6/6, `chunk` 0/6, as
  predicted. `chunk` is 14x slower than `fast` (19 GB/s).
- Per step at 137K: 16 layers x 1.0 ms = 16 ms, plus the drafter's layer (five one-token passes, about 2.7 ms), so
  about 19 ms against about 2 ms at 1K. Under the predicted 20-40 ms.
- **Decision: the writing-attention lever closes.** `fast` is under 2x `decode1` at all points but two (2.0 at 25K and
  246K), and `decode1` runs at 83-89 % of the card's bandwidth. A verify kernel that reads each key tile once for all
  6 rows could at best bring `fast` down to about `decode1`: about 7 ms per step at 137K (about 12 %), 4 ms at 64K.
  Recorded as a known option, below the bar.
- **What is left of the slowdown:** if a step at 1K takes about 33 ms (90 tokens/s at about 3 tokens per step),
  attention alone predicts about 57 tokens/s at 137K and 44 at 246K, not the 41 and 26 measured on 10-05. The rest
  is elsewhere: fewer tokens accepted per step on that text, or a per-step cost outside attention that grows with
  context. Next: measure writing at fixed contexts on the R314 server, with tokens per step from the server's own
  draft-acceptance counts.

## Writing at fixed context lengths on the server (registered 03:05 EDT, before the run)

Run: `scripts/run-20261017-write-rate.sh` brings up one context-lane server: campaign 24's flags, 832-token pieces,
TP2, MTP5, INT4 draft head and shortlist, exact cache. Then `scripts/probe-write-rate-vs-context.py` writes two
512-token answers (end of text ignored) at 1K, 32K, 64K, 100K, 137K, 200K and 246K. The prompts come from one ledger
text, so each is a prefix of the next. `copy` copies the first 30 records, the same text at every length. `story` is
a short story unrelated to the ledger. From the server's draft counters, per request: steps, tokens per step, and
writing time per step.

- **Predictions:** about 28-36 ms per step at 1K. Attention alone adds about 17 ms at 137K and 32 ms at 246K (the
  kernel times above, 16 layers plus five drafter passes); predicted growth within 30 % of that. Tokens per step
  steady across lengths within 15 % for each task (`copy` higher than `story`).
- **Decision:**
  - Growth per step within 30 % of the attention-only figure, and tokens per step steady: the slowdown is explained
    (attention, already near the card's bandwidth, plus what the text does to acceptance), and the long-context
    writing lever closes.
  - Growth more than 1.3x the attention-only figure at 137K and 246K: profile one writing step at 200K to find the
    rest.
  - Tokens per step falling more than 15 % from 1K to 137K on `copy`: look at the drafter at long context (its
    attention layer, the shortlist).
