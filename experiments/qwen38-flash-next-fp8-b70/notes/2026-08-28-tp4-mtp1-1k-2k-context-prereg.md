# Flash-Next TP4 native-MTP1 1K/2K context preregistration

Date: 2026-08-28

## Purpose and evidence boundary

Fill the two missing practical TP4/EP4/eager/text/native-MTP1 context cells at
1,024 and 2,048 active prompt tokens. MTP1 already passed the 512-token and
exact-4K Grade-C quality screens. These two cells complete a coherent MTP1
sequence at x0/1K/2K/4K without changing or rerunning any captured speed row.

This arm is capped at two fresh server boots and exactly two model requests per
boot. The second request is an identical repeat sentinel. It is not a second
performance sample. Nothing here may lower, replace, or reinterpret an
existing throughput or quality result.

## Frozen server identity

- model `Qwen/Qwen3.8-Flash-Next-FP8`, revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`, from the verified local-NVMe
  tree `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`;
- vLLM `1372c62d975c554f4b465c8299bc5f3295301ceb`;
- kernel checkout `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`;
- exact loaded hybrid stage
  `/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70`, build head
  `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- TP4/EP4, eager, graph off, text only, native MTP1, one sequence, 64 maximum
  batched tokens, prefix caching and async scheduling off;
- BLHNC automatic-precision KV, exactly `376569856` cache bytes / 32 blocks;
- selective UVA placement of the PLE n-gram and input embeddings, 12.22 GiB
  reported per rank;
- `enable_thinking=false` where chat templating applies; no diagnostics or
  performance-oriented changes.

The 1K server is configured at 1,536 tokens on port 19648. The 2K server is
configured at 3,072 tokens on port 19649. Both use attempt 1 and unique run,
cache, compile, and RPC paths. Launchers:

- `tools/launch-tp4-ep4-eager-mtp1-1536-headroom32.sh`;
- `tools/launch-tp4-ep4-eager-mtp1-3072-headroom32.sh`.

## Frozen artifacts

- shared base launcher SHA-256
  `62b40c9268a665727ff3946a621e4fcd2db072ed0bd4595dde7a6a006083ccb7`;
- 1K wrapper SHA-256
  `068b5e2008fdbfcd2baa7fe7c9a12914c4c2035f5ea117dbb6a5f3e67565dbc6`;
- 2K wrapper SHA-256
  `3b31b00c7b7636bb5f32c5bf8c4fbf6bf97b10dc0f7b058114b3646b4887b245`;
- legacy exact-1K harness SHA-256
  `d590c63c87b1e664417b4198dbbb873cbe4f252509fa8f9fc50830efca2b4cf4`;
- formal exact-depth harness SHA-256
  `8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067`;
- exact-depth fixture SHA-256
  `c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d`;
- 1K MTP0 receipt SHA-256
  `32d10c76e3cae156c2f167d1c429565944b61e8400a4c9b1a22457f9cbbc037b`;
- 2K MTP0 repeat-v2 receipt SHA-256
  `ecfbd7bf09fc2637bbee9be4658e1febc8ec8cc19f6f61c71864a615a2b25794`.

The frozen MTP0 output authorities are:

- 1K legacy deterministic completion text SHA-256
  `5f40744644b98ddd58a0c202fe855af324c0b1c33e1a6275afd74c12488f89f0`;
- 2K exact-depth output-token-ID SHA-256
  `5fd297f79da317b0741140cccb52fb710f89dfd1444effe9068b806b0300e57e`.

## Ordered execution

For each cell, acquire the host/GPU locks through the launcher and require all
of its exact model/source/runtime hashes, four idle B70s, four-rank collective
preflight, staged imports and schemas, four placement receipts, exactly 32
cache blocks, sufficient configured capacity, correct served identity, and a
healthy API. Snapshot `/metrics` immediately before and after every request.

### 1K boot

Run the legacy deterministic fixture twice with no warmup, requested prompt
setting 1,038, observed prompt usage exactly 1,024, 256 output tokens,
concurrency one, salt `context-r1`, and seed 20260606. Both responses must have
the frozen MTP0 text hash and must match each other. Per-request metric deltas
must show positive MTP1 draft and accepted-token counts and zero cached prompt
tokens.

### 2K boot

After a complete 1K teardown and clean-card check, run the formal exact-depth
fixture twice at depth 2,048, configured capacity 3,072, 128 output tokens,
adapter `vllm`, temperature zero, seed one, no prompt truncation, no special
tokens, and cache disabled. Both receipts must pass every built-in exact-depth
gate, contain the frozen MTP0 output-token-ID hash, and match each other.
Per-request metric deltas must again prove positive MTP1 draft and accepted
tokens and zero cached prompt tokens.

Tear down immediately after request two on each boot. The complete arm is
capped at 60 minutes GPU wall time.

## Stop rules and frozen interpretation

Stop immediately on any identity, placement, cache, capacity, health, token
count, finish-reason, output-hash, cache-zero, MTP-counter, timeout, API,
host-health, or teardown mismatch. If 1K teardown is incomplete, do not launch
2K. Do not raise the 300-second engine worker-response timeout and do not reuse
a server across contexts.

A pass adds only two `lab-screened`, Grade-C/research context cells. It does
not change speed claims, establish deployment readiness, or raise the MTP1
evidence ceiling. A failure or timeout is retained as a bounded result and
does not alter the already certified MTP0, MTP1-512, or MTP1-4K rows.

## Attempt 1 result

The 1K boot passed every frozen identity, import, four-rank collective,
placement, cache, capacity, and health gate. Reading the local-NVMe model made
the two 131-shard load phases substantially shorter than the earlier external
disk path; every rank completed model loading in about 101 seconds. The server
reported 32 blocks, 4,468 cache tokens, and 2.91x calculated capacity at the
configured 1,536-token length.

The first and only model request did not return output. After first-use shape
initialization, the request reached the unchanged 300-second worker-response
gate in `sample_tokens`. The server's preserved scheduler receipt showed 768
computed prompt tokens, 64 scheduled tokens, zero output tokens, no common
prefix blocks, and one speculative token selected for scheduling. The API then
closed. Request 2 was not sent, and the separate 2K boot was not launched, as
required by the stop rules.

The API completed its own shutdown, but the launcher and workers needed the
launcher's existing cleanup path to be triggered after they remained present.
After cleanup there were no model processes or listeners, and all four cards
were discoverable. The host journal named no B70 event in the run window. It
did contain corrected receiver-link events for the local NVMe device; these
are disclosed without assigning them as the cause.

This classifies TP4/eager/native-MTP1/active-1K as a retained bounded negative
on this exact identity. Active-2K remains missing, not failed. Existing MTP1
512 and exact-4K passes are unchanged. Compact receipt:
`data/20260828-tp4-mtp1-1536-context-attempt1-bounded-negative.json`.
