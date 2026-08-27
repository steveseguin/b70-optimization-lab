# Flash-Next TP4 MTP0 configured-4352 exact-4K preregistration

Date: 2026-08-27

## Purpose and frozen identity

This additive arm fills the 4,096-active-context text cell after the
protocol-v2 2K retry passed. It changes exactly one server parameter from the
accepted configured-3,072 identity: `max_model_len=4352`. The value is the
smallest 64-token-block-aligned capacity that fits the largest sealed request,
exactly p4096 plus o256.

Everything else remains frozen: official FP8 revision
`bcd9f01ddc9cff2316eb84281bebcd5b058bddce`, vLLM
`658965050f259999e635b52a850004a3771cd644`, kernels
`2f829747503c77d4814834dffd0840fb1dd9f75a`, staged runtime
`runtime-core-moe-negidguard-b70`, TP4/EP4, eager/graph-off, MTP0, text-only,
BF16 activation, Triton MoE, `allgather_reducescatter`, one sequence,
64 maximum batched tokens, prefix caching off, async scheduling off, the exact
12.25-GiB selective host-placement recipe, 0.92 GPU utilization, fixed
201,326,592-byte BLHNC automatic KV cache, and block size 64. No diagnostic
flag is allowed.

Launcher SHA-256 values before execution:

- base launcher: `99c4b9e3835d746e7ff58b50779c0c20a0d3d219632ad1889114b157502f4ecb`;
- configured-4,352 wrapper:
  `54d62bcf5e3a45603f87bc3be65b4ff991f4fea08ed60cd70df7d1c57d4d2d69`.

The run directory is new and immutable:
`qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1-attempt1`. Use port 19640.

## Offline calibration seal

The pinned local tokenizer produced these unique exact-depth settings:

- quality `--long-context-tokens 4372`: 4,084 raw prompt tokens and exactly
  4,096 chat/server prompt tokens with thinking disabled; prompt text SHA-256
  `ad9ee84cea592b52351c0fe0139e999c0e1b7626849489a5e9bbd5d6a840c935`,
  raw token IDs
  `d00cfefbc2b1f7c84b7eeb929734897e9fab321834b9a115ad20a7e01396c230`,
  and chat token IDs
  `be0d9a84a04234aab913352753fb84cb99d239a66417c4d98798b1dbbfeab8be`;
- legacy comparison `--prompt-tokens 4223`: exactly 4,096 server prompt tokens
  for salts `context-r1`, `context-r2`, and `context-r3`; calibrated token-ID
  SHA-256 values are
  `f1afffbb7c87474ddf7b163291266947bc0247e9c89827441d6c766b746922f6`,
  `fcae4e8fa2710436b9ef419686d2bb67333a2a81160bec2e0f15e2876a150d72`,
  and `050c7e92e4e30a541f48233ddca5a35a5d55b5052bcdbbde2b07650c69523161`
  respectively;
- formal fixture selected depth-4,096 token-array SHA-256 is
  `aedf2eb779bfa4aad8f533c644ca94646977deae1c10221bff592f06785c76d0`;
  planned request-payload SHA-256 is
  `2d92a2857d5cf45c3dcbc9d856cba714e2a36003295159fb5fcf1a8effb930be`.

The retained exact-depth fixture SHA-256 is
`c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d`.
Harness SHA-256 values are:

- quality suite:
  `3350671d03fa7c08e579df8bef9affbee51a3cf2f160a9d120c7166c0012c678`;
- exact-depth suite:
  `8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067`;
- legacy comparison:
  `0703d8f0564cab625183a02f010d238c8456d2e9e6aac04f4b8e11f81c8d6ae0`.

## Frozen gates and order

1. The server must report configured maximum 4,352, at least 4,352 available
   cache tokens, all four exact 12.22-GiB placement receipts, the expected
   approximately 31.27-GiB per-rank model footprint, and a healthy models
   endpoint. If the fixed cache cannot satisfy this, preserve a bounded
   negative; do not silently enlarge it.
2. Run the protocol-v2 short/repeat/needle suite once with 16 fixed-set
   repeats, thinking disabled, calibrated filler 4,372, and the attempt-2 2K
   quality result as baseline. Require the same five prescribed short passes
   with no new failure, exact 16/16 prescribed repeat output with one hash,
   exactly 4,096 server prompt tokens for the exact needle, exact needle
   output, and zero cached and created-cache tokens throughout. The process is
   expected to exit 1 only because the inherited full-suite result is 5/7.
3. Only if quality passes the incremental gates, run the sealed formal
   p4096/o128 exact-depth request. Require usage prompt 4,096, zero cached
   tokens, no truncation or context shift, 128 returned token IDs, length stop,
   and a valid 100-event/99-interval window.
4. Only if the formal gate passes, run three no-score p4096/o256/c1 comparison
   requests, one for each frozen salt, with no harness-added warmups after the
   prerequisite gates. Each must report exactly 4,096 prompt and 256 completion
   tokens. These rates use the retained legacy after-first-text accounting;
   the formal row remains the cache-zero authority.
5. Stop normally and retain request order, logs, responses, hashes, identity,
   and shutdown evidence. A result can fill only the TP4/EP4, MTP0, eager,
   graph-off, text, active-context-4,096 cell. It cannot promote the packet
   while short quality remains 5/7.

Stop before speed interpretation on any source/runtime mismatch, capacity
below 4,352, new short failure, repeat divergence, nonzero cache reuse, needle
failure, or formal depth-gate failure. The prior 512, 1K, and 2K results remain
unchanged regardless of this arm's outcome.

## Result

Attempt 1 preserved the frozen identity. It reported exactly 4,352 configured
tokens, 7,121 cache tokens, four 12.22-GiB placement receipts, and 31.27 GiB
per rank. The quality suite matched every 2K short and repeat output, passed
the prescribed repeat 16/16 with one hash, and returned the exact needle at
4,096 server prompt tokens with cached and created-cache counts zero.

The formal p4096/o128 row passed every gate at zero cached tokens. Its
conventional 99-interval rate was `4.456026475 tok/s`, TTFT was `217.909692 s`,
and all 128 requested token IDs were returned with a length stop. The three
legacy after-first-text p4096/o256 rows measured `5.298983875`, `5.233664732`,
and `5.161604624 tok/s`, median `5.233664732 tok/s`; median TTFT was
`123.391275 s`. All three returned the same 256-token output hash.

The application and all four workers completed controlled shutdown, with the
known post-manager API message and one resource-tracker cleanup item; no
process or listener remained. This fills the exact-4K selector as
research-screened. The inherited 5/7 short boundary still prevents promotion.
Receipt: `data/20260827-tp4-mtp0-4352-context-screen.json`.
