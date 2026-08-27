# Flash-Next TP4 MTP4 configured-4352 exact-4K preregistration

Date: 2026-08-27

## Purpose and preservation boundary

The configured-512 MTP4 arm became healthy, matched all 26 bounded MTP0
comparisons, held 16/16 fixed-set repeats, accepted 1,716/1,716 cumulative
draft tokens, and measured a `20.727176372 tok/s` median. It did not test MTP4
at 4K. This additive arm asks whether the fastest short-screen depth also
qualifies for the user-selected practical 4,096-token deployment ceiling.

Nothing in this arm may replace or lower any captured MTP0-4/configured-512
cell or the existing exact-4K MTP3 result. A failure becomes a bounded result.
The selective host placement is preserved: the PLE and input-embedding shards
stay resident in pinned system RAM and GPU-addressable through UVA after cold
load; serving does not stream them from the external checkpoint tree.

## Frozen identity

- model `Qwen/Qwen3.8-Flash-Next-FP8` revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- vLLM `1372c62d975c554f4b465c8299bc5f3295301ceb`;
- staged XPU runtime built from kernel source
  `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- TP4/EP4, allgather/reduce-scatter, eager/graph-off, text-only;
- MTP4, configured maximum 4,352, one sequence, batched-token cap 64;
- fixed automatic-KV BLHNC cache `341266432` bytes: exactly 29 current-source
  shared-pool blocks, one block above the 28-block admission/null floor;
- prefix caching and async scheduling off;
- selective UVA placement of `ple_embedding.ngram_embedding.weight` and
  `embed_tokens.weight`, 13,117,911,040 bytes (12.22 GiB reported) per rank;
- `enable_thinking=false` on every chat request; no diagnostics.

Launcher:
`experiments/qwen38-flash-next-fp8-b70/tools/launch-tp4-ep4-eager-mtp4-4352.sh`.
Campaign: `qwen38-flash-next-fp8-tp4-ep4-eager-mtp4-4352-r1`, attempt 1,
port 19642. The new run and cache roots are immutable.

Frozen SHA-256 values:

- base launcher: `b8fedb333865a9727baf8de2670b580a0656554035415ce36d94fc38154eb39c`;
- MTP4/4352 wrapper: `bb05718f24a678e81504810002087361ef93d5bae64728c8eff2514ade70e9ed`;
- quality suite: `3350671d03fa7c08e579df8bef9affbee51a3cf2f160a9d120c7166c0012c678`;
- exact-depth suite: `8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067`;
- comparison harness: `d590c63c87b1e664417b4198dbbb873cbe4f252509fa8f9fc50830efca2b4cf4`;
- exact-depth fixture: `c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d`.

The sealed MTP0 4K quality baseline is
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1-attempt1/quality-v2-short-and-4k.json`,
SHA-256 `a458747f6c84b1adbfbf4dff77ab8c5ffabf5446a990fc6711a66ae1119389b4`.

## Cache proof

The current source and retained MTP3 evidence establish one shared-pool block
as 11,767,808 bytes and the attention alignment as 832 tokens. MTP4/4352 needs
27 usable blocks plus one reserved null/admission block. The hard floor is 28
blocks or 329,498,624 bytes. The frozen allocation is exactly 29 blocks or
341,266,432 bytes, retaining one spare block. The first boot must still verify
the alignment, exact reported block count, capacity at least 4,352, and healthy
generation.

## Frozen gates and order

1. Require the exact source, runtime, model, four-card, and launcher identity.
   The real server command must contain exactly one MTP4 configuration,
   configured maximum 4,352, and cache bytes `341266432`.
2. Require a healthy models endpoint, all four 12.22-GiB placement receipts,
   exactly 29 cache blocks, and reported cache capacity of at least 4,352
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
response, capacity miss, or service instability stops publication and is
retained with its exact scope. Passing fills only TP4/EP4, eager, MTP4,
active-context 4,096, text, automatic-KV. It remains Grade C while the inherited
short target quality is 5/7 and cannot be called deployment-ready or
record-eligible.

## Attempt 1 result

Attempt 1 preserved the frozen identity, became healthy, and passed cache
admission. All four ranks again reported 32.06 GiB model allocation and 12.22
GiB selective host placement. The fixed 29-block allocation exposed 4,674
cache tokens and 1.07x maximum concurrency at the 4,352-token limit.

The preregistered quality gate failed at the long-context request. The last
captured scheduler state had 3,904 computed tokens, a 64-token scheduled chunk,
92.86% cache usage, and four speculative slots. After five one-minute wait
messages, the engine's 300-second worker-response deadline expired during
token sampling, the request returned HTTP 500, and the service shut down. The
helper writes its JSON only after every stage, so no partial quality JSON was
produced; this attempt receives no short, repeat, baseline-parity, or exact-4K
quality credit and no timing rows were authorized.

The API and engine ended, but workers lingered until the operator stopped the
launcher. During that cleanup the kernel logged compute/copy engine resets and
follow-on messages on all four B70 addresses. No process or listener remained,
and all four devices were discoverable afterward, but a post-reset four-rank
collective was not run. Two earlier corrected Samsung NVMe endpoint reports
were unrelated and had zero uncorrected status.

This exact MTP4/active-4K selector is quarantined. Raising only
`VLLM_EXECUTE_MODEL_TIMEOUT_SECONDS` is not a safe retry because the workers
remained unresponsive and card engines reset during cleanup. The successful
MTP4/512 and MTP3/4K cells remain unchanged. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp4-4352-attempt1-bounded-negative.json`.
