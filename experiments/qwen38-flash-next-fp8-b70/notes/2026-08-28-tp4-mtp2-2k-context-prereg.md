# Flash-Next TP4 native-MTP2 exact-2K context preregistration

Date: 2026-08-28

## Purpose and evidence boundary

Classify the missing TP4/EP4/eager/text/native-MTP2 active-2K matrix cell with
one fresh server boot and at most two identical requests. MTP2 already passes
its configured-512 and exact-4K endpoints; the working 4K recipe established
the 32-block cache allocation used here. The exact-2K MTP0 output authority is
sealed. This arm changes no existing speed, quality, preferred recipe, or the
separate MTP3 active-2K quarantine.

## Frozen server identity

- model `Qwen/Qwen3.8-Flash-Next-FP8`, revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`, from
  `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`;
- vLLM `1372c62d975c554f4b465c8299bc5f3295301ceb`;
- kernel checkout `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`;
- loaded stage
  `/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70`, built from
  `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- TP4/EP4, eager, graph off, text only, native MTP2, one sequence, 64 maximum
  batched tokens, prefix caching and async scheduling off;
- BLHNC automatic-precision KV, exactly `376569856` bytes / 32 blocks, the
  cache allocation already proven by the passing exact-4K MTP2 arm;
- selective UVA placement of the PLE n-gram and input embeddings, 12.22 GiB
  reported per rank;
- configured maximum 3,072, port 19660, attempt 1, no diagnostics.

Launcher:
`tools/launch-tp4-ep4-eager-mtp2-3072-headroom32.sh`.

## Frozen artifacts

- shared base launcher SHA-256
  `62b40c9268a665727ff3946a621e4fcd2db072ed0bd4595dde7a6a006083ccb7`;
- MTP2 exact-2K wrapper SHA-256
  `0d2c6acfba44fe4dced88a024e5d75b80aa21f6bb3f03d9b65f9a124a99b3124`;
- exact-depth harness SHA-256
  `8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067`;
- exact-depth fixture SHA-256
  `c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d`;
- MTP0 exact-2K repeat-v2 receipt SHA-256
  `ecfbd7bf09fc2637bbee9be4658e1febc8ec8cc19f6f61c71864a615a2b25794`;
- frozen MTP0 output-token-ID SHA-256
  `5fd297f79da317b0741140cccb52fb710f89dfd1444effe9068b806b0300e57e`.

## Ordered execution

1. Require the launcher's exact model/source/runtime hashes, clean source
   checkouts, four expected idle B70s, fresh four-rank collective, staged
   imports and schemas, four 12.22-GiB placement receipts, exactly 32 cache
   blocks, reported capacity of at least 3,072 tokens, correct served identity,
   and a healthy API.
2. Snapshot endpoint counters, then run the sealed exact-depth fixture once at
   depth 2,048 through the `vllm` adapter with temperature zero, seed one,
   ignored EOS, no prompt truncation, no special tokens, cache disabled, and
   128 requested output tokens. Add no warmup.
3. Require exactly 2,048 prompt and 128 output tokens, a length stop, zero
   cached tokens, the frozen MTP0 token-ID hash, a complete 100-event /
   99-interval decode window, and positive MTP2 drafted and accepted-token
   counter deltas.
4. Only if request one passes, repeat the identical request once. Require the
   same gates, the same MTP0 hash, and exact token-array equality with request
   one. The repeat is a determinism sentinel, not another independent speed
   sample.
5. Capture final counters and bounded shutdown/card/listener evidence. The arm
   is capped at one boot, two requests, and 35 GPU wall minutes.

## Stop rules and frozen interpretation

Stop immediately on any identity, placement, cache, capacity, health, token
count, finish-reason, output-hash, cache-zero, MTP-counter, response-gate, API,
host-health, or teardown mismatch. If request one fails, do not send request
two. Do not raise the fixed 300-second engine response gate, change cache
allocation, add a warmup, or reuse another server.

A pass adds only the TP4/eager/native-MTP2/active-2K cell as `lab-screened`,
Grade-C research evidence. A stop is retained as a bounded quarantine. Neither
outcome changes MTP2/512, MTP2/exact-4K, MTP3/active-2K, any featured result,
or any prior captured speed.
