# Gemma 4 26B A4B Q8 LAN service on the two-B70 host: 16K slots, 4 per card, deterministic oneDNN

Date: 2026-10-09/10. Host: steve-TURIND8-2L2T (192.168.2.45, two Arc Pro B70, 15 GiB RAM, kernel 7.0.0-38).
Binary: host oneAPI 2026.1 compat build of the record aggregate
(`~/src/llama.cpp-gemma-c926-oneapi2026.1-compat/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2`), see the 2026-09-07 gate.
Units: `gemma4-26b-q8-quad-backends.service` + `gemma4-26b-q8-quad-frontdoor.service` with host drop-ins in
`/etc/systemd/system/<unit>.service.d/two-b70-host.conf`. Public API `http://192.168.2.45:8000/v1`, model `gemma4-26b-a4b-q8`.

## Shape chosen

| | before (runbook shape) | now |
| --- | --- | --- |
| slots per card | 2 x 64K | 4 x 16K |
| concurrent generations (2 cards) | 4 | 8 |
| MTP draft length (n_max / n_min) | 3 / 2 | 1 / 1 |
| LLAMA_PREFILL_UBATCH_SIZE | 2048 | 1024 |
| oneDNN | on (nondeterministic) | on, `GGML_SYCL_DNNL_DETERMINISTIC=1` |
| --ctx-checkpoints | 0 (prompt cache never reused on this SWA model) | 8 (multi-turn prefix reuse works) |
| card memory after load | 31.8 GB | 30.1-30.4 GB |

## Measurements (one card, 2K-token prompts unless stated)

Decode tok/s per stream by active streams, record draft length 3 vs draft length 1:

| active streams | draft 3 (P2..P6 servers) | draft 1 (P4 server, deterministic oneDNN) |
| ---: | ---: | ---: |
| 1 | 116 | 105 |
| 2 | 84 (168 aggregate) | 73 (146) |
| 3 | 28 (85) | - |
| 4 | 26 (106) | 56 (224) |
| 6 | 23 (136) | - |

Cause of the cliff at 3 streams: the Gemma MoE fast kernels (`ggml-sycl.cpp` multi-token `mul_mat_id` paths, lines
~6526, 7200, 7324) accept at most 8 tokens per step. Draft length 3 = 4 tokens per sequence, so 3+ sequences fall off
the fast path. Draft length 1 = 2 tokens per sequence, 4 sequences = 8. Raising that kernel limit to 16 is the next
lever (not attempted).

Prefill (single stream, tok/s): 8K prompt 1522 (stock oneDNN) / 1473 (deterministic oneDNN) / 1392 (oneDNN off);
15K prompt ~1520 / 1393 / 1316. ubatch 512 costs ~10% more (1365 at 8K). Prefill of one slot stalls the other slots'
decode to 3-9 tok/s (llama.cpp has no token budget per step; BATCH_SIZE 1024 did not help).

Prompt cache: with `--ctx-checkpoints 0` every request logged "forcing full prompt re-processing (SWA)"; with 8,
turn 2 of a 6K-context chat has TTFT 0.4 s instead of 4.4 s (6036 cached tokens).

Memory: 4 x 16K with prefill ubatch 2048 loads at 31.4 GB but the VMM pool then OOM-aborts under 4 concurrent 2K
prompts (`ggml_sycl_pool_vmm::alloc`); with prefill ubatch 1024 it idles at 30.2 GB and survives 4 x 8K concurrent
prompts (30.4 GB). 5 x 16K = 32.2 GB (too tight), 6 x 16K needs ubatch 512. A `logprobs` request dequantizes the
262144-row output head (~1.5 GB temp) and OOM-aborts the backend at any of these shapes, so the frontdoor now rejects
`logprobs`/`top_logprobs` (new env `FRONTDOOR_REJECT_JSON_FIELDS` in `scripts/openai-lan-frontdoor.py`).

## Determinism

Test: the same cold 6040-token "summarize this random document" prompt, temperature 0, `cache_prompt=false`, sent
sequentially to an idle server.

| config | distinct outputs |
| --- | --- |
| record flags, draft 3 | 3 of 5 |
| record flags, draft 1 / no speculation | 4 of 5 / 3 of 5 |
| every custom LLAMA_*/GGML_SYCL flag off, no speculation, SYCL graph off | 3 of 5 |
| same + flash attention off (1 slot) | 4 of 5 |
| same + `GGML_SYCL_DISABLE_DNN=1` | **1 of 5** |
| record flags, draft 1, `GGML_SYCL_DISABLE_DNN=1` | 1 of 6, 1 of 4, 1 of 3 (seeds 4, 6, 7) |
| record flags, draft 1, `GGML_SYCL_DNNL_DETERMINISTIC=1` (patched gemm.hpp) | 1 of 6, 1 of 4, 1 of 3 |

So the run-to-run variance seen since July (notes/2026-07-02 variance diagnostic) is the stock oneDNN matmul.
Patch: `ggml/src/ggml-sycl/gemm.hpp` in the compat tree, after `set_scratchpad_mode`:
`if (ggml_sycl_get_env("GGML_SYCL_DNNL_DETERMINISTIC", 0)) { primitive_attr.set_deterministic(true); }`
(oneDNN 3.11 API). Rebuilt only `libggml-sycl.so` (new sha256 e98584bc…); `llama-server` itself unchanged.
The text canary passed 32/32 with oneDNN off; the deterministic-oneDNN build served the same answers.

Still NOT deterministic by construction: output can differ when the same prompt is (a) batched with other slots
(4 identical prompts at once gave 4 different summaries, each a valid greedy decode differing at near-ties) or
(b) resumed from a prompt-cache checkpoint instead of processed cold. Both are the kernel-selection-by-M problem the
FP8 lane solved with batch-invariant overlays; the llama.cpp SYCL kernels here have no such guarantee. Short, low-entropy
answers (facts, code, JSON) were identical across all of these conditions in every test; the divergences appeared on the
high-entropy summary prompt.

## Operational

- Start order `GPU_INDICES="1 0"` with START_STAGGER_S: card 0 (PCI 03:00.0) hung in `load_tensors` for 14 min on the
  first start of the day (GT reset on kill, evidence `/mnt/fast-ai/bench-results/gpu-fault-20261009T2126/`); later loads
  were clean (24-30 s).
- A crashed replica takes the whole backends unit down and systemd restarts both replicas (Restart=on-failure, 15 s).
- Stop: `sudo systemctl disable --now gemma4-26b-q8-quad-frontdoor.service gemma4-26b-q8-quad-backends.service`.

## 2026-10-10 addendum: throughput recipe for the 600K-message batch job, recipe switcher

User need: a shape that maximises total tokens/s for many concurrent API clients (messages ~2K, hard max 16K), plus a
shape that maximises single-session decode. Switcher: `scripts/gemma4-26b-two-b70-recipe.sh {throughput|balanced|single|status}`
with drop-ins in `deploy/systemd/two-b70-host/` (non-interactive: `SUDO_ASKPASS=... ` makes it use `sudo -A`).

Closed-loop client (`workers` concurrent requests back-to-back, distinct prompts, temperature 0), one card:

| shape | workers | 300 in / 150 out total tok/s | 1000 in / 100 out total tok/s | mean latency |
| --- | ---: | ---: | ---: | ---: |
| balanced: 4 x 16K, draft 1 | 4 | 588-592 | 1067 | 2.9 s |
| **throughput: 8 x 4K, no draft** | 8 | **626-643** | **1127** | 5.5 s |
| 8 x 4K, draft 1 on the 16-token fast path (patched) | 8 | 490 | 979 | 7.3 s |
| throughput, oversubscribed | 12 | 619 | | 8.3 s |

Both cards through the LAN frontdoor, throughput recipe: 16 workers 1229 tok/s (300/150), 2229 tok/s (1000/100);
24 workers 1263 tok/s. Prod-health ok, canary 32/32, cold repeats identical (3/3). Card memory 30.8-30.9 GB.
Time split at 300/150: ~1/3 prefill (~1500 tok/s/card), ~2/3 decode (~200-260 tok/s/card aggregate); both are the
remaining levers and both are kernel work.

16-token kernel experiment (negative): `ggml-sycl.cpp`/`mmvq.cpp` patched so `LLAMA_SYCL_MUL_MAT_ID_MAX_TOKENS` (default 8,
max 16) lifts the fast-path guards, with a 16-wide variant of the two grouped Q8_0 kernels and matching caps in
`src/llama-graph.cpp` (`llama_moe_fused_max_tokens()`). Built and run: at 8 streams x 2 tokens the per-stream decode fell
to 17 tok/s (vs 32 without speculation and 55 at 4 streams), so the 16-token path is slower than the generic path for
decode. Default 8 keeps the old behaviour (verified: determinism and 590 tok/s unchanged). Patch kept in the compat tree
and inert; a real 16-token kernel would need the per-(token,slot) weight re-reads removed.

Single recipe: 1 slot x 16K per card, draft 3, prefill ubatch 2048 (single-sequence MTP fast paths stay on). Not
re-measured today; July record 125 tok/s on one stream at this shape.

## 2026-10-10 00:10 addendum: throughput recipe tuning pass (installed)

A/B at 8 streams on one card (decode-only aggregate, 100-token prompts, 256 out): baseline 270-276 tok/s;
`LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_GROUPED_Q8_0_REORDER=1` 289-305 (+rowpack 305-309) but 95 at 4 streams (vs 197) and
no gain in the mixed closed-loop load (613-617 vs 610-643) -> not enabled. PER_SLOT 275, BF16_DIRECT 266, ubatch 512 249.
Host CPU is not a bottleneck (87% idle with both cards loaded; one 85% thread per server).

Prompt-cache reuse for a shared instruction prefix (both cards, 16 workers, 300-token message, 150 out):
| prefix | placement | requests/s | cached tok/s |
| --- | --- | ---: | ---: |
| none | - | 3.0-3.2 | 0 |
| 400 tokens | system message | 2.6-2.7 | ~890 |
| 400 tokens | inside the user message | not reused | ~0 |
| 1500 tokens | system message | 1.9 (vs ~1.0 uncached at 1800 in) | ~2230 |
The server checkpoints at the start of the last user message, so a shared prefix is reused only when it is a separate
system (or earlier) message. `--checkpoint-min-step` default 8192 does not matter for this.

Host RAM: with `--cache-ram 2048 --ctx-checkpoints 8` the two servers reached ~4 GB RSS each under 16-way load with
checkpoints, MemAvailable fell to 1.1 GiB and earlyoom SIGTERMed python clients (it prefers python). Recipe now uses
`--cache-ram 512 --ctx-checkpoints 2` (peak RSS 4.2 GB each with a system prefix, MemAvailable >= 5.8 GiB; 0.7-0.8 GB
without prefixes) and the frontdoor unit has `OOMScoreAdjust=-900`. Control reruns: 1230-1313 total tok/s both cards.
