# Why does writing slow down 2-3x at long context? (preregistration, 2026-10-17 02:27 EDT)

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

## Writing at fixed context lengths on the server (registered 02:35 EDT, before the run)

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

## Result, writing at fixed lengths (02:39-02:47 EDT, server W832; `data/2026-10-17-write-rate/write-W832.json`)

512 tokens per answer; ms per step = writing time / draft-and-check steps (server counters):

| Context | copy tok/s | copy tokens/step | story tok/s | story tokens/step | ms per step (copy / story) |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1K | 136.5 | 5.27 | 70.5 | 2.73 | 38.6 / 38.3 |
| 32K | 80.0 | 4.95 | 41.5 | 2.56 | 61.5 / 61.6 |
| 64K | 67.0 | 5.44 | 29.8 | 2.43 | 81.1 / 81.2 |
| 100K | 55.2 | 5.64 | 23.3 | 2.38 | 101.8 / 101.9 |
| 137K | 45.5 | 5.64 | 18.6 | 2.32 | 123.4 / 123.7 |
| 200K | 34.9 | 5.62 | 13.9 | 2.24 | 160.8 / 161.4 |
| 246K | 28.9 | 5.45 | 13.2 | 2.49 | 188.2 / 188.4 |

- Time per step is the same for both tasks at every length (within 0.6 ms), so it depends on the context only.
  Tokens per step: copy steady (4.95-5.64), story falls 15-18 % by 137-200K.
- **Predictions missed:** 38.6 ms at 1K (predicted 28-36). Growth of 85 ms at 137K and 150 ms at 246K, against 17 and
  32 predicted from the attention kernel alone (5x). So by the registered rule this is the "profile" branch, and
  acceptance (copy steady) is not the cause.
- The cause of most of it showed up before a profile was needed (next section): the server's verify-rows overlay.
  Six separate calls per layer predict about +50 ms at 137K and +87 ms at 246K (16 x 6 x the one-row time). The rest,
  about 0.24 ms per 1,000 tokens (32 ms at 137K, 58 at 246K), is still unexplained and gets profiled after the change
  below.

## Found during the run: the server checks drafts with six separate attention calls (02:42 EDT)

The context-lane server runs `--fa-verify-rows` (overlay `b70-fa-verify-rows` 0.1.0; also in the TP2 package). Above
1,536 keys it computes the 6 checked rows as six separate one-token decode calls per layer, so that every row equals
plain decoding. The kernel timing above shows six separate calls cost about 6x one decode (each re-reads the cache
from memory), where one launch of the same six rows costs 1.8-2.0x (the rows' reads of each key tile overlap in L2).
At 100K that is 16 x (2.44 - 0.74) = 27 ms per step. The September note (`2026-09-17-fa-multirow-verify-plan.md`)
expected one launch to save "only launches"; one launch is what lets L2 catch the repeat reads. The one-pass
`paged_decode_multiq` kernel built then (one card, R312d-c, +10-17 % at 16-30K) is not in R314.

Why the kernel library's own one-launch path (`fast`) cannot simply be used: it picks the number of key splits for
a batch of six rows, and a lone row picks it for a batch of one (`get_num_splits`, flash_api.cpp). The two differ
between about 3,009 and 24,512 keys (counted from the formula, 32 Xe cores, pages of 832); all 14 timed points above
happened to fall outside that band, so their 6/6 does not cover it. A row's key partition depends only on its own key
count and the split count.

**Change:** `b70-fa-verify-rows` 0.2.0, `B70_FA_VERIFY_ROWS_ONE_LAUNCH=1` (off by default; off = 0.1.0 behaviour).
It makes one launch of the decode kernel with the six rows as one-token pseudo-sequences, and passes the split count
each lone row's call would pick, computed on the host from the same `max_seqlen_k - back` the per-row calls use.
When the six rows would not all pick the same count, it falls back to the per-row calls; the formula says that
happens at 130 of the 260,603 lengths from 1,542 to 262,144 (0.05 %).

## Check and server comparison (registered 02:47 EDT, before either run)

1. **Census** (`scripts/census-verify-rows.py`, R314 image, card 0, split counts from the overlay file itself):
   every length from 1,537 to 30,000 in steps of 7, plus 30-34K, 99.0-99.6K, 199.0-199.3K and 245.0-245.3K. Pages of
   832 and 1,280; 6 rows each, against six lone-row calls. Must hold: the one-launch arm equals the lone rows 6/6 at
   every length where it is used, and the kernel's own fast path differs exactly where the formula says the split
   counts differ (validates the mirror). Any one-launch mismatch stops the change.
2. **Server** (if the census holds): a fresh server with the same flags plus `B70_FA_VERIFY_ROWS_ONE_LAUNCH=1`, and
   the same write probe. Must hold: all 14 answers (512 tokens each, 1K-246K) bitwise equal to this morning's W832
   answers.
   - **Prediction:** ms per step unchanged at 1K (the overlay is off below 1,536 keys), and 20-35 % lower from 32K
     up (about 46 / 72 / 108 ms at 32K / 100K / 200K, against 61.5 / 101.8 / 160.8).
   - **Decision:** adopt for the context lane, and propose it for the TP2 package, if the answers are identical and
     the time per step falls 10 % or more at 64K and above. Otherwise record and close.

## Result, census (02:51 EDT, card 0, kernel log clean; `data/2026-10-17-verify-census/attn-r314.json`)

| Pages | Lengths | one launch used | one launch = lone rows, 6/6 | kernel fast path = lone rows, 6/6 |
| ---: | ---: | ---: | ---: | ---: |
| 832 | 4,209 | 4,190 | **4,190** | 1,206 |
| 1,280 | 4,209 | 4,190 | **4,190** | 1,206 |

- **The one-launch mode holds:** every row equal to the lone-row call wherever it was used, both page sizes. The other
  19 lengths per page are split-count boundaries, where the overlay falls back to the per-row calls.
- The kernel's own fast path is lone-row equal at only 1,206 of 4,209 lengths. With 32 Xe cores, the formula never
  predicted equality where the rows differed (0 false "equal"). Its 73 false "differ" are split counts that differ
  but give the same key partition (e.g. 31 and 32 splits over the same number of tiles), or rows under 2,048 keys,
  which the kernel keeps unsplit.
- **Found and fixed before any server run:** the kernel interface's core-count helper returns 20 on this torch (it
  looks for per-slice fields torch does not expose); the card has 32 (`gpu_subslice_count`). The first draft of
  0.2.0 compared the two and would have refused to start. It now uses `gpu_subslice_count`. For one sequence with 2
  key/value heads, the lone-row split count is the same for 20 and 32 cores at every length up to 262,144 (checked),
  so the census result does not depend on it.

## Result, server comparison (03:00-03:12 EDT, server W832o; `data/2026-10-17-write-rate/write-W832o.json`)

Same flags as W832 plus `B70_FA_VERIFY_ROWS_ONE_LAUNCH=1` (log: "enabled (one launch per verify call)"):

| Context | ms per step, 0.1.0 | one launch | change | copy tok/s | story tok/s |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1K | 38.6 | 38.5 | -0.3 % | 136.5 -> 136.9 | 70.5 -> 70.8 |
| 32K | 61.5 | 42.9 | **-30 %** | 80.0 -> 114.7 | 41.5 -> 59.6 |
| 64K | 81.1 | 47.6 | **-41 %** | 67.0 -> 114.3 | 29.8 -> 50.8 |
| 100K | 101.8 | 52.9 | **-48 %** | 55.2 -> 106.2 | 23.3 -> 44.8 |
| 137K | 123.4 | 58.4 | **-53 %** | 45.5 -> 96.2 | 18.6 -> 39.3 |
| 200K | 160.8 | 67.3 | **-58 %** | 34.9 -> 83.4 | 13.9 -> 32.9 |
| 246K | 188.2 | 75.0 | **-60 %** | 28.9 -> 72.5 | 13.2 -> 33.2 |

- **Exact:** all 14 answers (512 tokens each) are bitwise equal to W832's. The step counts and accepted tokens are
  identical too.
- **Faster than predicted** (predicted 20-35 %, about 46 / 72 / 108 ms at 32K / 100K / 200K; measured 42.9 / 52.9 /
  67.3). Growth above 1K is now 0.15 ms per 1,000 tokens. The attention kernel alone predicts 0.13 (16 layers of the
  one-launch call, plus the drafter's layer). So the unexplained 0.24 ms per 1,000 tokens in W832 was the per-row path
  too: its calls ran slower in the server than one call does alone. Nothing is left to profile on this question.
- **Decision (as registered): adopt for the context lane.** Every context-lane server from now on runs with
  `B70_FA_VERIFY_ROWS_ONE_LAUNCH=1`. Propose the same for the TP2 package; that package ships the same 0.1.0
  overlay, so the change needs its own gates and the owner's go before release. The 10-05 figures (41 tok/s at 137K,
  26 at 246K) were this overlay's cost.
- Not affected: prompt reading (first-token times equal within 0.1 s at every length), calls under 1,536 keys, and
  batches of several requests (the overlay only touches one-request verify calls).
