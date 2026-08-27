# Flash-Next TP4 MTP3 configured-4352 exact-4K preregistration

Date: 2026-08-27

## Purpose and preservation boundary

The configured-512 MTP3 arm became healthy, matched all 26 bounded MTP0
comparisons, held 16/16 fixed-set repeats, and measured a variable
`14.888789794 tok/s` median. It did not test MTP3 at 4K. This additive arm is
the first deployment-shaped MTP3 qualification: a 4,096-token prompt plus 256
output tokens on TP4/EP4, with the user-selected practical context ceiling.

Nothing in this arm may replace or lower the captured MTP0, MTP1, or MTP3/512
cells. A failure becomes a new bounded result. The existing selective host
placement is preserved: the PLE and input-embedding shards stay resident in
pinned system RAM and GPU-addressable through UVA after cold load; serving does
not stream them from the external checkpoint tree.

## Frozen identity

- model `Qwen/Qwen3.8-Flash-Next-FP8` revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- vLLM `1372c62d975c554f4b465c8299bc5f3295301ceb`;
- staged XPU runtime built from kernel source
  `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- TP4/EP4, allgather/reduce-scatter, eager/graph-off, text-only;
- MTP3, configured maximum 4,352, one sequence, batched-token cap 64;
- fixed automatic-KV BLHNC cache `294195200` bytes: exactly 25 current-source
  shared-pool blocks, one block above the 24-block admission/null floor;
- prefix caching and async scheduling off;
- selective UVA placement of `ple_embedding.ngram_embedding.weight` and
  `embed_tokens.weight`, 13,117,911,040 bytes (12.22 GiB reported) per rank;
- `enable_thinking=false` on every chat request; no diagnostics.

Launcher:
`experiments/qwen38-flash-next-fp8-b70/tools/launch-tp4-ep4-eager-mtp3-4352.sh`.
Campaign: `qwen38-flash-next-fp8-tp4-ep4-eager-mtp3-4352-r1`, attempt 1,
port 19639. The new run and cache roots are immutable.

Frozen SHA-256 values:

- base launcher: `b8fedb333865a9727baf8de2670b580a0656554035415ce36d94fc38154eb39c`;
- MTP3/4352 wrapper: `405f2b102f848a9b07ff95ccc23ae9729eb972f000c728a175241950554f3797`;
- quality suite: `3350671d03fa7c08e579df8bef9affbee51a3cf2f160a9d120c7166c0012c678`;
- exact-depth suite: `8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067`;
- comparison harness: `d590c63c87b1e664417b4198dbbb873cbe4f252509fa8f9fc50830efca2b4cf4`;
- exact-depth fixture: `c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d`.

The sealed MTP0 4K quality baseline is
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1-attempt1/quality-v2-short-and-4k.json`,
SHA-256 `a458747f6c84b1adbfbf4dff77ab8c5ffabf5446a990fc6711a66ae1119389b4`.

## Frozen gates and order

1. Require the exact source, runtime, model, four-card, and launcher identity.
   The real server command must contain exactly one MTP3 configuration,
   configured maximum 4,352, and cache bytes `294195200`.
2. Require a healthy models endpoint, all four 12.22-GiB placement receipts,
   exactly 25 cache blocks, and reported cache capacity of at least 4,352
   tokens. Stop as a fit result if admission fails; do not silently enlarge or
   move weights.
3. Run the protocol-v2 short/repeat/needle suite once against the sealed MTP0
   4K baseline, with 16 repeats, filler setting 4,372, thinking disabled, and
   no cache reuse. Require all 26 comparisons, one repeat hash, exactly 4,096
   server prompt tokens for the needle, and complete usage. The inherited 5/7
   strict result may make the helper nonzero; the comparison gates are
   authoritative.
4. Only after quality parity, run the sealed exact p4096/o128 formal fixture.
   Require usage prompt 4,096, 128 returned token IDs, length stop, zero cached
   tokens, and a valid 100-event/99-interval window.
5. Only after the formal gate, run the three exact p4096/o256/c1 comparison
   rows with salts `context-r1`, `context-r2`, and `context-r3`, requested
   prompt setting 4,223, and no added warmups. Require p4096/o256 usage,
   complete responses, and the accepted target hash. Report every row and do
   not suppress variance.
6. Capture cumulative MTP endpoint counters after timing, then stop normally.
   Preserve shutdown and host-health evidence. Do not call cumulative counters
   per-row acceptance evidence.

Any new quality mismatch, repeat divergence, nonzero cache reuse, incomplete
response, capacity miss, or service instability stops promotion and is retained
with its exact scope. Passing fills only TP4/EP4, eager, MTP3, active-context
4,096, text, automatic-KV. It remains Grade C while the inherited short target
quality is 5/7 and cannot be called deployment-ready or record-eligible.
