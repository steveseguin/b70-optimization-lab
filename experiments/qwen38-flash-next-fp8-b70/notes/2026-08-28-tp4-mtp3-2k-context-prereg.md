# Flash-Next TP4 native-MTP3 exact-2K context preregistration

Date: 2026-08-28

## Purpose and evidence boundary

Classify the missing TP4/EP4/eager/text/native-MTP3 active-2K matrix cell with
one fresh server boot and at most two identical model requests. MTP3 already
passed its configured-512 and exact-4K Grade-C gates. The exact-2K MTP0 output
authority is sealed. This arm changes no existing speed, quality, or preferred
recipe and does not retry the separate MTP1 active-1K stop.

## Frozen server identity

- model `Qwen/Qwen3.8-Flash-Next-FP8`, revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`, from
  `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`;
- vLLM `1372c62d975c554f4b465c8299bc5f3295301ceb`;
- kernel checkout `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`;
- loaded stage
  `/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70`, built from
  `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- TP4/EP4, eager, graph off, text only, native MTP3, one sequence, 64 maximum
  batched tokens, prefix caching and async scheduling off;
- BLHNC automatic-precision KV, exactly `294195200` bytes / 25 blocks, the
  cache allocation already proven by the passing exact-4K MTP3 arm;
- selective UVA placement of the PLE n-gram and input embeddings, 12.22 GiB
  reported per rank;
- configured maximum 3,072, port 19650, attempt 1, no diagnostics.

Launcher:
`tools/launch-tp4-ep4-eager-mtp3-3072-headroom25.sh`.

## Frozen artifacts

- shared base launcher SHA-256
  `62b40c9268a665727ff3946a621e4fcd2db072ed0bd4595dde7a6a006083ccb7`;
- MTP3 exact-2K wrapper SHA-256
  `4912beb2980049c89b3f66f59669fbcb414284dc0e215d722a0206fd9ebca9b3`;
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
   imports and schemas, four 12.22-GiB placement receipts, exactly 25 cache
   blocks, reported capacity of at least 3,072 tokens, correct served identity,
   and a healthy API.
2. Snapshot endpoint counters, then run the sealed exact-depth fixture once at
   depth 2,048 through the `vllm` adapter with temperature zero, seed one,
   ignored EOS, no prompt truncation, no special tokens, cache disabled, and
   128 requested output tokens. Add no warmup.
3. Require exactly 2,048 prompt and 128 output tokens, a length stop, zero
   cached tokens, the frozen MTP0 token-ID hash, a complete 100-event /
   99-interval decode window, and positive MTP3 drafted and accepted-token
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

A pass adds only the TP4/eager/native-MTP3/active-2K cell as `lab-screened`,
Grade-C research evidence. A stop is retained as a bounded quarantine. Neither
outcome changes MTP3/512, MTP3/exact-4K, any featured result, or any prior
captured speed.

## Outcome

The single authorized boot passed every startup gate and exposed 3,657 cache
tokens from the exact 25-block allocation. Request one completed with exactly
2,048 prompt tokens, 128 output tokens, zero cached tokens, a length stop, and
a complete 100-event/99-interval window. Native MTP3 was active: endpoint
counters increased by 54 drafts, 162 draft tokens, and 76 accepted tokens.
The diagnostic conventional rate was `5.931661200811598 tok/s`, with
`150.76991040899884 s` TTFT.

The lane-specific frozen target-parity gate failed. The candidate token-array
hash was
`4a56559f49ea6e38b09a24bb7bb2888f81237de4b4cb0acbd9a3fd400d943f71`,
not the sealed MTP0 hash
`5fd297f79da317b0741140cccb52fb710f89dfd1444effe9068b806b0300e57e`;
the arrays first differ at zero-based generated-token index 4. The generic
depth/transport harness correctly passed its own checks, but that does not
override the separately preregistered MTP0 oracle. Request two was therefore
not sent.

This closes TP4/eager/native-MTP3/active-2K as a Grade-D quarantine with no
speed, quality, or deployment credit. It is a scoped deterministic target-
parity mismatch, not a universal semantic-quality claim. Controlled shutdown
left no listener or residual model process, and all four cards remained
discoverable. MTP3/512, MTP3/exact-4K, and every captured speed remain
unchanged. Structured receipt:
`../data/20260828-tp4-mtp3-3072-context-attempt1-parity-quarantine.json`.
