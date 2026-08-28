# Flash-Next TP4 native-MTP2 active-1K preregistration

Date: 2026-08-28

## Purpose and evidence boundary

Classify the missing TP4/EP4/eager/text/native-MTP2 active-1K matrix cell
with one fresh server boot and at most two identical requests. MTP2 already
passes its configured-512 and exact-4K cells; active 2K is separately
quarantined on target parity. This is additive coverage only. It may not
lower, replace, or reinterpret any captured speed, quality result, or
preferred recipe.

The prior MTP1 active-2K teardown window recorded resets on all four cards.
Therefore this arm requires the base launcher's clean-device checks and fresh
four-rank collective preflight; device discovery alone is not sufficient.

## Frozen server identity

- model `Qwen/Qwen3.8-Flash-Next-FP8`, revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`, from the verified local-NVMe
  tree `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`;
- vLLM `1372c62d975c554f4b465c8299bc5f3295301ceb`;
- kernel checkout `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`;
- loaded stage
  `/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70`, built from
  `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- TP4/EP4, eager/graph-off, text only, native MTP2, one sequence, 64 maximum
  batched tokens, prefix caching and async scheduling off;
- BLHNC automatic-precision KV, exactly `376569856` bytes / 32 blocks;
- selective UVA placement of the PLE n-gram and input embeddings, with 12.22
  GiB required per-rank placement receipts;
- configured maximum 1,536, port 19662, attempt 1, no diagnostics.

The base launcher rejects unexpected identity inputs and clears inherited
`VLLM_*` variables before exporting the frozen runtime settings. The engine
therefore retains its default 300-second worker-response gate; the request
client is separately fixed at 360 seconds.

Fail-closed launcher:
`tools/launch-tp4-ep4-eager-mtp2-1536-headroom32.sh`.

## Frozen artifacts and authority

- shared base launcher SHA-256
  `62b40c9268a665727ff3946a621e4fcd2db072ed0bd4595dde7a6a006083ccb7`;
- MTP2 active-1K wrapper SHA-256
  `0723a802f2a5779e6577d33b8aa682da4c44218c19657e1bbeed706cf84aad27`;
- legacy deterministic harness `scripts/bench-openai-concurrency.py` SHA-256
  `d590c63c87b1e664417b4198dbbb873cbe4f252509fa8f9fc50830efca2b4cf4`;
- MTP0 active-1K compact receipt SHA-256
  `32d10c76e3cae156c2f167d1c429565944b61e8400a4c9b1a22457f9cbbc037b`;
- raw MTP0 `context-r1` authority SHA-256
  `ad8de7521078654fe12f0f0c247b6c4f34897faa188e3ccd993e9dc04a07c874`;
- frozen MTP0 completion-text SHA-256
  `5f40744644b98ddd58a0c202fe855af324c0b1c33e1a6275afd74c12488f89f0`.

The MTP0 authority used vLLM `658965050` and a smaller cache allocation,
whereas this current-source MTP2 cell uses vLLM `1372c62d` and 32 blocks.
Consequently, a hash mismatch is a scoped cross-lane parity quarantine, not
isolated proof that MTP2 caused a semantic difference.

The frozen client invocation uses `/home/steve/.venvs/vllm-xpu/bin/python`
with `scripts/bench-openai-concurrency.py`, base URL
`http://127.0.0.1:19662`, tokenizer
`/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`, and flags:

```text
--prompt-tokens 1038 --shared-prefix-tokens 0 --prompt-salt context-r1
--output-tokens 256 --concurrency 1 --warmups 0
--timeout 360 --seed 20260606
```

Only `--output-json` changes between the two frozen filenames below.

## Ordered execution

1. Require the launcher's exact model/source/runtime hashes, clean source
   checkouts, four expected idle B70s, successful fresh four-rank collective,
   staged imports and schemas, four placement receipts, exactly 32 cache
   blocks, at least 1,536 reported tokens of capacity, served identity, and
   healthy API. Take a new kernel-journal cutoff before preflight; only events
   after that cutoff adjudicate this arm. Abort before loading on any preflight
   failure or new B70 event.
2. Snapshot `/metrics`, then use the pinned vLLM interpreter to run the legacy
   harness once with requested prompt setting 1,038, salt `context-r1`, 256
   output tokens, concurrency one, no warmup, harness base seed 20260606, and
   explicit harness flag `--timeout 360`. Write only
   `bench-context1k-o256-c1-r1.json`. Require observed usage of exactly 1,024
   prompt and 256 completion tokens, a complete stream, and the frozen MTP0
   completion-text hash.
   If the harness does not complete, it must not leave a partial JSON; retain a
   separate `request1-failure.txt` with the client status and elapsed bound.
3. Require the metrics delta to show positive MTP2 draft and draft-token
   counters plus positive accepted-token deltas at both positions zero and
   one. Require `vllm:prompt_tokens_cached_total` to be present before and after
   the request with a delta of zero; a missing cache metric is a stop. The
   legacy harness itself does not retain the cache field.
4. Only after every request-one gate passes, repeat the identical request once
   to `bench-context1k-o256-c1-r2.json`. Require the same usage, MTP0 hash,
   exact text equality, positive isolated MTP2 counters at both positions, and
   zero cached-token delta. On a failed repeat retain `request2-failure.txt`
   instead of a partial JSON. This is a determinism sentinel, not a second
   performance sample.
5. Capture final counters, raw hashes, the bounded journal artifact, shutdown,
   listener/process census, and four-card discovery. The arm is capped at one
   boot, two requests, and 30 GPU wall minutes.

## Stop rules and frozen interpretation

Stop immediately on any identity, collective, placement, cache, capacity,
health, token-count, output-hash, cache-zero, MTP-counter, response-gate, API,
new post-cutoff host event, or teardown mismatch. If request one fails, do not
send request two. Do not raise the fixed worker-response/client bounds, change
cache allocation, add a warmup, or reuse another server.

A pass adds only TP4/eager/native-MTP2/active-1K as Grade-C research evidence.
A stop is retained as a bounded quarantine. Neither outcome changes MTP2/512,
MTP2/active-2K, MTP2/exact-4K, MTP1, MTP3, any featured result, or any prior
captured speed.
