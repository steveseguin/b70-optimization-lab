# Flash-Next TP4 MTP2 exact-4K 32-block control preregistration

Date: 2026-08-27

## Question and preservation boundary

The first TP4/MTP2 exact-4K arm passed all matched-quality gates and its formal
p4096/o128 row, then stopped during the first p4096/o256 row at 3,904 computed
tokens with 90% cache use. The later native-MTP1 exact-4K recipe completed the
same gates and all three p4096/o256 rows with a 32-block cache allocation.

This control changes only the MTP2 fixed cache allocation from 21 to 32 blocks.
It asks whether materially lower cache pressure removes the MTP2 service
boundary. It may not replace or lower any configured-512 result, the retained
MTP2/21-block quarantine, or the preferred MTP3/4K result.

## Frozen identity

- model `Qwen/Qwen3.8-Flash-Next-FP8` revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- vLLM `1372c62d975c554f4b465c8299bc5f3295301ceb`;
- live XPU-kernel checkout
  `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`;
- staged runtime built from kernel source
  `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- TP4/EP4, eager/graph-off, text-only, MTP2, native recurrent mode off;
- configured maximum 4,352, one sequence, batched-token cap 64;
- automatic-KV BLHNC cache `376569856` bytes: exactly 32 current-source
  shared-pool blocks, 12 blocks above the 20-block MTP2 hard floor;
- prefix caching and async scheduling off;
- selective UVA placement of `ple_embedding.ngram_embedding.weight` and
  `embed_tokens.weight`; serving keeps those shards in pinned host RAM and
  does not stream from the external checkpoint tree;
- `enable_thinking=false` on every chat request; no diagnostics;
- unchanged 300-second engine worker-response deadline.

Launcher:
`experiments/qwen38-flash-next-fp8-b70/tools/launch-tp4-ep4-eager-mtp2-4352-headroom32.sh`.
Campaign: `qwen38-flash-next-fp8-tp4-ep4-eager-mtp2-4352-r1`, attempt 2,
port 19645. The attempt-2 run and cache roots must not already exist.

Frozen SHA-256 values:

- base launcher: `b8fedb333865a9727baf8de2670b580a0656554035415ce36d94fc38154eb39c`;
- headroom32 wrapper: `07ba18d8eb4009eb60df714825e856ea7e0119afb5a001e13d9a648241f8427e`;
- sealed MTP0 4K baseline:
  `a458747f6c84b1adbfbf4dff77ab8c5ffabf5446a990fc6711a66ae1119389b4`.

## Frozen gates and order

1. Require a clean host census, all four devices, the exact source/runtime and
   launcher hashes, and the launcher's fresh four-rank communication preflight.
2. Require a healthy API, all four selective-placement receipts, exactly 32
   cache blocks, and reported capacity of at least 4,352 tokens. Do not resize
   the pool or move more weights if admission fails.
3. Run the existing protocol-v2 short/repeat/exact-4K suite once against the
   sealed MTP0 baseline. Require 26/26 comparisons, 16/16 one-hash repeats,
   exactly 4,096 server prompt tokens for the needle, and zero cached and
   created-cache tokens on every audited request. The inherited target 5/7 may
   produce the expected helper exit 1.
4. Run the sealed formal p4096/o128 fixture and require all 25 checks, zero
   cached tokens, 128 returned token IDs, and a valid 99-interval window.
5. Run three separately salted p4096/o256/c1 rows with no harness-added
   warmups. Require complete usage and the accepted target hash; retain every
   row and all variance.
6. Capture cumulative MTP counters, then stop normally and retain shutdown,
   device-discovery, and run-window health evidence.

## Frozen interpretations

- A pass closes a separate `TP4/eager/native-MTP2/active-4K/headroom32`
  Grade-C support recipe. It supersedes the coverage blank/quarantine for
  practical use while retaining the 21-block attempt as disclosed history.
- A pass does not prove 32 blocks is minimal or that cache is the general cause
  of every deeper-MTP failure. MTP3 remains the preferred 4K recipe unless the
  complete metrics prove otherwise.
- A repeat stop near 3,904 computed tokens with the larger pool is strong
  evidence against simple cache pressure for this exact MTP2 arm.
- Any mismatch, repeat divergence, cache reuse, incomplete response, service
  stop, or unhealthy cleanup is preserved as a bounded result. Do not retry by
  changing only a timeout.
- Nothing from this arm can overwrite, lower, or withdraw a captured speed,
  quality result, packet, or prior submission.
