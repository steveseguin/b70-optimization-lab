# Speculation matches on every test, but its recurrent kernel is not bit-identical to plain decoding (2026-10-04)

## In plain words

The owner's rule is exact and deterministic **by construction**. Checked against that rule today, the single-user
recipe's drafting does not meet it yet:

- When the model checks drafted words, the recurrent layers use a "speculative" kernel. A direct census on the R310
  image shows that kernel is **not bit-identical to plain one-word-at-a-time decoding**: the first checked row
  matches, every later row differs in the last bit (at most 1.5e-5 on outputs, up to 4.9e-4 on the carried state).
- On every suite we have, the shipped depth-5 recipe still gives the same answers as no drafting (12 of 12, 64 of
  64, 8 of 8 long prompts, and the acceptance suites). So nothing published is known to be wrong. But it is exact
  **by test, not by construction**, and a tie could in principle fall the other way.
- The proof that it matters: checking nine copied words in one step (longer copy drafts) changed answers
  (11 of 12, 5 of 8, 55 of 64), while the same server without long drafts was exact. The longer the accepted run,
  the further the carried state drifts from plain decoding.

What **is** exact by construction today: everything with drafting off. That is the many-users mode (374 / 536 /
630 tok/s at 16 / 32 / 64 users) and one user without drafting (33.9 tok/s on two cards).

## The census

`scripts/qwen38-fp8-gdn-spec-batch-census.py` (repaired for R310 today), two-card shapes, one card.
Data: `data/2026-10-04-kernel-census/`.

| Question | Result |
|---|---|
| Do the first rows change with the number of rows in the verify (2 to 33)? | No: bit-identical to the 6-row call, outputs, states and conv line |
| Do requests in one call affect each other (1 to 64 requests of 6 rows)? | No: each equals itself alone, in any order |
| Is each verify row equal to the same token decoded alone, one token at a time? | **Row 0 yes; rows 1 and later no** (max 1.5e-5); prefix states differ from prefix 2 (max 2.4e-4 to 4.9e-4) |
| Is it deterministic? | Yes, every repeat identical |

The image has no switch for this: `VLLM_XPU_GDN_NATIVE_SPEC_*_SERIAL_EXACT` are not referenced anywhere in R310.

Also settled by census today (same data folder): the normalisation layers as the server compiles them are
row-invariant for 1 to 128 rows; paged attention decode is batch-invariant for contexts up to 1,645 tokens at up to
64 sequences (it is not at 6,524, which is what the per-sequence overlay handles).

## Longer copy drafts (K = 9), the run that exposed it

`MU_MODE=copydraft MU_COPY_K=9`, data `data/2026-10-04-copy-draft/fp8-copydeep-k9-20261004/`.

| Arm (same launch: synchronous, 9 verify slots, head at 5) | Strict | Long prompts | Short ladder | Long-prompt decode (median) |
|---|---|---|---|---:|
| Control, no long drafts | 12/12, 87.95 tok/s | 8/8 | 64/64 | 87.1 tok/s |
| Long copy drafts (249 placed, 4.02 of 9 accepted on average) | **11/12** | **5/8** | **55/64** | 110.0 tok/s (+26 %) |

The speed is real and matches the sizing. The answers are not exact, so it is not a result.

## What is being done

A kernel patch so the speculative path rounds its carried state exactly where plain decoding does, making every
verify row and every stored prefix state bit-identical to decoding one token at a time. With that:

1. the shipped single-user drafting becomes exact by construction (census: `rows_equal_decode` true for every row);
2. longer copy drafts become exact too, and the +26 % on long prompts can count;
3. drafting with several users can be tested again on a sound footing.

It needs a new image (R313, built from R310 plus the patch), the census, then the full gates and a speed check.
Until then the published single-user numbers stand as "identical on every test", which is what the packages say.

## R313: the patch works (19:45 EDT)

Patch `patches/vllm-xpu-kernels-gdn-spec-decode-exact-r313-20261004.patch`: in the speculative kernel, the state
carried into the next verify row is the same fp16-rounded value that is stored in the slot (eight lines). Image
R313 is R310 with only `_xpu_C` replaced (`data/2026-10-04-r313/`).

| Check on R313 | Result |
|---|---|
| Census, two-card and one-card shapes, 2 to 33 verify rows, three previous-accepted counts | **Every row and every prefix state bit-identical to one-token decode** (74 of 74 cases; on R310: 0). Row-count and batch invariance kept |
| Shipped recipe, strict suite twice | 12/12 and 12/12, 90.31 and 90.25 tok/s (R310 the same hour: 90.40 and 90.27). No cost |
| Synchronous pipeline, strict twice | 12/12 and 12/12, 88.00 and 88.11 tok/s |

So on R313 the recurrent layers' part of speculation is exact by construction. What still has no census for the
verify shape (6 rows against one row at a time): the attention kernel for verify rows at short contexts and the
recurrent layers' small FP16 projection. Those are next.

**Longer copy drafts are still not exact on R313** (same counts as on R310: 11/12, 5/8, 55/64, +25.8 % on long
prompts), so the kernel rounding was not their problem. The pattern in the answers is sharp: after a step that
accepts six or more drafted tokens, the second row of the following step is wrong. That points at something in the
engine or another kernel that mishandles more than five accepted tokens; it is being traced.

