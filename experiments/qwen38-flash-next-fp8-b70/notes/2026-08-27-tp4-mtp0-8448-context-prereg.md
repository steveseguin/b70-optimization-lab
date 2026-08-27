# Flash-Next TP4 MTP0 configured-8448 exact-8K preregistration

Date: 2026-08-27

## Purpose and frozen identity

This additive arm fills the 8,192-active-context text cell after the exact-4K
arm passed. It changes exactly one server parameter from the accepted
configured-4,352 identity: `max_model_len=8448`, the smallest
64-token-block-aligned value that fits p8192 plus o256.

Every accepted performance setting remains frozen: official FP8 revision
`bcd9f01ddc9cff2316eb84281bebcd5b058bddce`, vLLM
`658965050f259999e635b52a850004a3771cd644`, kernels
`2f829747503c77d4814834dffd0840fb1dd9f75a`, staged runtime
`runtime-core-moe-negidguard-b70`, TP4/EP4, eager/graph-off, MTP0, text-only,
BF16 activation, Triton MoE, `allgather_reducescatter`, one sequence, 64
maximum batched tokens, prefix caching off, async scheduling off, exact
12.25-GiB selective host placement, 0.92 GPU utilization, fixed
201,326,592-byte BLHNC automatic KV cache, and block size 64. No diagnostic
flag is allowed.

The fixed cache is not enlarged. The four retained boots expose a consistent
hybrid-cache plan: 18 shared-pool blocks, 832 aligned attention tokens per
block, and five fixed state blocks per maximum-length request. The formula
`floor(18 / (ceil(max_model_len / 832) + 5) * max_model_len)` reproduces the
reported 1,536, 3,949, 6,144, and 7,121-token capacities. At 8,448 it predicts
9,504 tokens and 1.125x concurrency. This prediction is not a pass: startup
must report at least 8,448 tokens or the arm stops without resizing cache.

Launcher SHA-256 values before execution:

- base launcher: `2907b6352fcbbdd6a9bb5225d5008af5bfcc324a1151183cf259962554523aa7`;
- configured-8,448 wrapper:
  `9a4ea26817718a84d214815a2547680bd6605f201be438a97ec152a99c8550df`.

The new run directory is
`qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-8448-r1-attempt1`; use port 19641.

## Offline calibration seal

- Quality `--long-context-tokens 8800` produces 8,180 raw prompt tokens and
  exactly 8,192 chat/server tokens with thinking disabled. Prompt text
  SHA-256 is `85733869d1fc157f63d86582fdd0227914cd034aa196ae6debc825a052d3ac01`,
  raw token IDs are
  `52b04142d62fb1601380f68b0ca58b822314ffdfcd4c7745396c9850fadc4ec0`,
  and chat/server token IDs are
  `720cc23b6fdc223595886d96b0726f3bb61dac250ae85b81ac2ed9901d2ac810`.
- Legacy `--prompt-tokens 8471` produces exactly 8,192 server prompt tokens
  for all three salts. Token-ID SHA-256 values are
  `67135a2c6a64f1ab4fcf9560abcb89d29d80475ad05ed3ed1d210ff5b66d03fb`,
  `c443f19430cb203fab99abae62cf427d1d84dc7127532a5382337a724cf8cd22`,
  and `0ad5acaa67ce3f5d1f6eff51ce7a47267a536371af7a891ec589ebf46e6baead`.
- Formal depth-8,192 token IDs are
  `6baa17bea14f0ecad7e4edf54a05256eafaef1d447a447569fd303371c671741`;
  the planned payload SHA-256 at configured capacity 8,448 is
  `d2c65090ce71e4db33b834b3de55a82a8c4c2f9485baaf94adb156ee686a0e1b`.

The exact-depth fixture remains
`c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d`.
Quality, formal, and legacy harness SHA-256 values remain
`3350671d03fa7c08e579df8bef9affbee51a3cf2f160a9d120c7166c0012c678`,
`8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067`,
and `0703d8f0564cab625183a02f010d238c8456d2e9e6aac04f4b8e11f81c8d6ae0`.
The baseline raw 4K quality JSON SHA-256 is
`a458747f6c84b1adbfbf4dff77ab8c5ffabf5446a990fc6711a66ae1119389b4`.

## Frozen gates and order

1. Require reported maximum 8,448, fixed cache bytes 201,326,592, at least
   8,448 reported cache tokens, all four exact 12.22-GiB placement receipts,
   approximately 31.27 GiB per rank, and a healthy models endpoint. Never
   resize cache inside this arm.
2. Run protocol-v2 short/repeat/needle quality with 16 fixed-set repeats,
   filler 8,800, thinking disabled, and the exact 4K raw quality JSON as
   baseline. Require the same five short passes with no new failure, every
   baseline comparison true, exact prescribed repeat 16/16 with one hash,
   exact needle output at 8,192 server prompt tokens, and zero cached and
   created-cache tokens throughout. Exit 1 is expected only from the inherited
   full-suite 5/7 boundary.
3. Only after the incremental quality gates pass, run formal p8192/o128.
   Require exact usage, cached tokens zero, no truncation or context shift, 128
   token IDs, length stop, and a valid 100-event/99-interval window.
4. Only after the formal gate passes, run three exact p8192/o256/c1 legacy
   comparisons with salts `context-r1` through `context-r3` and no
   harness-added warmups after prerequisite gates. Require exact 8,192/256
   usage. The formal row is the cache-zero authority.
5. Stop normally and retain order, hashes, identity, and shutdown evidence.

Any identity/capacity mismatch, new short failure, repeat divergence, nonzero
cache reuse, needle failure, or formal failure stops the arm before speed
interpretation. Prior 0/1K/2K/4K results remain unchanged in every outcome.
