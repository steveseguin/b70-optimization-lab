# Flash-Next TP4 MTP1 configured-4352 headroom-32 preregistration

Date: 2026-08-27

## Purpose and preservation boundary

The configured-512 MTP1 arm became healthy, matched all 26 bounded MTP0
comparisons, held 16/16 fixed-set repeats, and measured a
`9.372254368 tok/s` median. It did not test MTP1 at 4K. This additive arm fills
the remaining TP4 eager MTP-depth cell at the user-selected 4,096-token
practical context ceiling.

The MTP2 and MTP4 one-spare exact-4K arms both stopped at 3,904 computed
tokens during a p4096/o256 request, while MTP3 passed. This arm therefore uses
a deliberately roomy 32-block fixed pool instead of optimizing for the
minimum cache. The extra allocation is only 359.125 MiB per rank and does not
change weights, selective host placement, source, or runtime. It is a
deployment-headroom screen, not a minimum-cache depth A/B.

Nothing in this arm may replace or lower a configured-512 cell or the existing
MTP3 exact-4K result. A failure becomes a bounded result. The PLE and input
embedding remain resident in pinned system RAM and GPU-addressable through UVA
after cold load; serving does not stream them from the external checkpoint
tree.

## Frozen identity

- model `Qwen/Qwen3.8-Flash-Next-FP8` revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- vLLM `1372c62d975c554f4b465c8299bc5f3295301ceb`;
- live XPU-kernel checkout
  `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`;
- staged XPU runtime built from kernel source
  `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- TP4/EP4, allgather/reduce-scatter, eager/graph-off, text-only;
- MTP1, configured maximum 4,352, one sequence, batched-token cap 64;
- fixed automatic-KV BLHNC cache `376569856` bytes: exactly 32 current-source
  shared-pool blocks;
- prefix caching and async scheduling off;
- selective UVA placement of `ple_embedding.ngram_embedding.weight` and
  `embed_tokens.weight`, 13,117,911,040 bytes (12.22 GiB reported) per rank;
- `enable_thinking=false` on every chat request; no diagnostics;
- quality-helper timeout 1,800 seconds; engine worker-response timeout remains
  the unchanged 300-second default.

This is native MTP1 with `MTP_EXACT=0` and the standard served name. It is not
the separate paused MTP1 exact-recurrent candidate, which uses a different
runtime stage and diagnostic identity.

Launcher:
`experiments/qwen38-flash-next-fp8-b70/tools/launch-tp4-ep4-eager-mtp1-4352-headroom32.sh`.
Campaign: `qwen38-flash-next-fp8-tp4-ep4-eager-mtp1-4352-r1`, attempt 1,
port 19644. The new run and cache roots are immutable.

Frozen SHA-256 values:

- base launcher: `b8fedb333865a9727baf8de2670b580a0656554035415ce36d94fc38154eb39c`;
- MTP1/4352 headroom wrapper: `acef80eded6336d9d776c29fceb351fec86d340133a22251e1bf2b8804fed5d2`;
- quality suite: `3350671d03fa7c08e579df8bef9affbee51a3cf2f160a9d120c7166c0012c678`;
- exact-depth suite: `8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067`;
- comparison harness: `d590c63c87b1e664417b4198dbbb873cbe4f252509fa8f9fc50830efca2b4cf4`;
- exact-depth fixture: `c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d`.

The sealed MTP0 4K quality baseline is
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1-attempt1/quality-v2-short-and-4k.json`,
SHA-256 `a458747f6c84b1adbfbf4dff77ab8c5ffabf5446a990fc6711a66ae1119389b4`.

## Cache proof and deliberate margin

The current source establishes one shared-pool block as 11,767,808 bytes and
the attention alignment as 832 tokens. MTP1/4352 needs 15 usable blocks plus
one reserved null/admission block: a 16-block hard floor. The usual one-spare
allocation would be 17 blocks. This arm freezes 32 blocks, exactly 376,569,856
bytes, giving 16 blocks over the hard floor. The first boot must verify the
832-token alignment, exactly 32 reported blocks, capacity at least 4,352, and
healthy generation. No result from this arm may be described as proving the
minimum cache requirement. Current-source arithmetic predicts about 9,284
reported cache tokens and 2.13x maximum concurrency; the boot receipt remains
authoritative.

## Frozen gates and order

1. Require the exact source, runtime, model, four-card, and launcher identity.
   The real server command must contain exactly one MTP1 configuration,
   configured maximum 4,352, and cache bytes `376569856`.
2. Require the launcher's four-rank communication preflight after the prior
   reset event. Then require a healthy models endpoint, all four 12.22-GiB
   placement receipts, alignment 832, exactly 32 cache blocks, and reported
   capacity of at least 4,352 tokens. Stop if preflight or admission fails; do
   not change placement, runtime, or cache mid-attempt.
3. Run the protocol-v2 short/repeat/needle suite once against the sealed MTP0
   4K baseline, with 16 repeats, filler setting 4,372, thinking disabled, no
   cache reuse, and helper timeout 1,800 seconds. Do not raise the engine's
   300-second worker-response deadline. Require all 26 comparisons, one repeat
   hash, exactly 4,096 server prompt tokens for the needle, and complete usage.
4. Only after quality parity, run the sealed exact p4096/o128 formal fixture.
   Require usage prompt 4,096, 128 returned token IDs, length stop, zero cached
   tokens, and a valid 100-event/99-interval window.
5. Only after the formal gate, run three exact p4096/o256/c1 comparison rows
   with salts `context-r1`, `context-r2`, and `context-r3`, requested prompt
   setting 4,223, and no added warmups. Require p4096/o256 usage, complete
   responses, and the accepted target hash. Report every row and variance.
6. Capture cumulative MTP endpoint counters after timing, then stop normally.
   Preserve shutdown and host-health evidence. Do not call cumulative counters
   per-row acceptance evidence.

Any quality mismatch, repeat divergence, nonzero cache reuse, incomplete
response, capacity miss, or service instability stops publication and is
retained with its exact scope. Passing fills only TP4/EP4, eager, MTP1,
active-context 4,096, text, automatic-KV with 32-block headroom. It remains
Grade C while inherited target quality is 5/7 and cannot be called
deployment-ready or record-eligible until a later clean-boot stability
confirmation. If a long request stops responding, preserve the scheduler
and service evidence, take no partial credit, and do not retry by changing
only a timeout.

## Attempt 1 result

Attempt 1 preserved the frozen native-MTP1 identity, passed the fresh
four-rank preflight, became healthy, and passed cache admission. The exact
32-block allocation reported 9,284 cache tokens and 2.13x maximum concurrency.
All ranks reported 32.06 GiB model allocation, 12.22 GiB selective host
placement, and 832-token alignment.

The complete quality gate passed: all 26 sealed MTP0 comparisons, 16/16
fixed-set repeats with one hash, the exact 4,096-token needle, and zero cached
or created-cache tokens across all 24 audited requests. The inherited strict
score remains 5/7, explaining the helper's expected exit 1. The formal exact
p4096/o128 gate passed all 25 checks at `3.471451019 tok/s` conventional with
`317.104665 s` TTFT.

All three no-warmup p4096/o256 rows completed with the accepted target hash.
They measured `8.904420575 / 8.868704697 / 9.581812274 tok/s` after first
text, median `8.904420575 tok/s`. Median TTFT was `232.079233 s`, median wall
output rate was `0.981050 tok/s`, and the decode rows span 8.01% of their
median. Cumulative session metrics accepted 528/539 draft tokens (97.96%).

The service then completed a controlled stop: all four workers and the API
finished, no process or listener remained, all four cards were discoverable,
and the kernel run window named no B70 address. This closes only the
TP4/eager/native-MTP1/active-4K/headroom32 Grade-C cell. It does not establish
the minimum cache, prove that cache pressure caused the MTP2/MTP4 stalls, or
make the recipe deployment- or record-ready. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp1-4352-headroom32-attempt1-result.json`.
