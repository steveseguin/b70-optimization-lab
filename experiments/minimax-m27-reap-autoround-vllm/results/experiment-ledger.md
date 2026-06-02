# Experiment Ledger

## 2026-05-31

- Created REAP-specific lane.
- Verified HF metadata and vLLM config construction only; no full model load yet.
- vLLM resolved architecture as `MiniMaxM2ForCausalLM`.
- vLLM mapped the checkpoint quantization to `inc`, matching the existing AutoRound/XPU path.
- HF token was not found in `HF_TOKEN`, `HUGGINGFACE_HUB_TOKEN`, `HUGGING_FACE_HUB_TOKEN`, or the default cached token path. The repo is public/ungated, so download can proceed unauthenticated, but authenticated HF would be preferable for speed and rate limits.
- Added a first-pass B70 int4 MoE config for REAP's `E=192,N=384` shape by mirroring the existing MiniMax `E=256,N=384` settings. This is a launch baseline, not a tuned result.
- Production MiniMax is currently running on `127.0.0.1:18080` with the LAN frontdoor on `0.0.0.0:8000`, and `xpu-smi` reports about 32.6 GiB used on each B70. Do not run REAP quality/bench until the production service is intentionally paused or another GPU set is available.
- Planned first gate:
  - download to `/mnt/fast-ai/llm-models/minimax-m2.7-reap-autoround-w4a16`
  - short quality smoke at `max_model_len=2048`
  - decode baseline at `p512n1536`, TP4, `max_num_seqs=1`, XPU graph enabled

No LocalMaxxing submission is eligible yet.

Download result:

- Completed download to `/mnt/fast-ai/llm-models/minimax-m2.7-reap-autoround-w4a16`.
- Stable recipe after timeout/DNS churn: `HF_HUB_DISABLE_XET=1 HF_DOWNLOAD_WORKERS=6 HF_DOWNLOAD_ATTEMPTS=0 scripts/download-model.sh`.
- `hf_xet` was available but did not progress reliably in this environment; keep XET disabled for this lane.
- Safetensor files: `23`.
- Safetensor bytes: `91,512,175,232` (`85.23 GiB`).
- `model.safetensors.index.json` references `23` files, with `0` missing.
- No `.incomplete` or `.lock` files remained in the local HF download cache.
- Local vLLM config construction from the downloaded path resolves:
  - architecture: `MiniMaxM2ForCausalLM`
  - model type: `minimax_m2`
  - dtype: `torch.float16`
  - quantization: `inc`

Production pause:

- Production was intentionally paused for REAP testing.
- Added reversible pause marker: `/home/steve/llm-optimizations/.pause-minimax-production`.
- Patched the production vLLM and LAN frontdoor wrappers to exit when that marker exists.
- Verified `minimax-vllm.service` and `minimax-openai-frontdoor.service` inactive, with ports `8000`, `18080`, and `18082` free during checks.

Bring-up fixes:

- First full load reached weights but failed warmup because the MiniMax logits WS path was hard-coded for `256` routed experts. REAP has `192`.
- Added B70 MoE configs for `E=192,N=384`:
  - `E=192,N=384,device_name=Intel(R)_Graphics_[0xe223],dtype=int4_w4a16.json`
  - `E=192,N=384,device_name=Intel(R)_Arc(TM)_Pro_B70_Graphics,dtype=int4_w4a16.json`
- Patched and rebuilt the llm-scaler INT4 MoE extension so the MiniMax logits top-k kernel dispatches `192` and `256` experts.
- Import check passed for `moe_forward_tiny_cutlass_nmajor_int4_u4_minimax_ws`.
- Short prompts corrupted under compiled prefill, generating token id `0`. Keeping decode compiled but setting `VLLM_XPU_SKIP_COMPILED_PREFILL=1` fixed the short-prompt corruption.

Quality status:

- Conservative graph path passed the semantic canary with `VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS=0` and `VLLM_XPU_SKIP_COMPILED_PREFILL=1`.
- Passing canary covered:
  - exact `REAP_OK_128GB` answer after `</think>`
  - Python signature `def median_latency_ms(...)`
  - speculative-decoding quality answer
- Latest known passing canary: `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/quality-smoke-20260531T173525Z.json`.
- CCL topology override canary also passed:
  - env: `CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK=0`
  - file: `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/quality-smoke-20260531T182225Z.json`
  - result: `passed=true`, `514` generated tokens, deterministic, no NUL/control/degenerate output
- Model load uses about `21.3 GiB` per B70 and reports about `132,352` KV-cache tokens at `max_model_len=2048`.

Decode benchmarks:

- Conservative baseline, `p512n1536`, TP4, graph decode:
  - log: `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260531T173728Z.log`
  - elapsed: `17.511 s`
  - total throughput: `116.95 tokens/s`
  - output throughput: `87.71 tokens/s`
- `CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK=0` sweep:
  - log: `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260531T181503Z.log`
  - elapsed: `17.381 s`
  - total throughput: `117.83 tokens/s`
  - output throughput: `88.37 tokens/s`
  - This is a small positive and now has a matching semantic canary pass.
- `MAX_BATCHED_TOKENS=1024` with a fresh cache failed startup with vLLM piecewise compile assertion: `Expected exactly one compiled range_entry for static shape compilation, but found 2`.

Easy-win sweep:

- Added experiment-wrapper support for preserving selected llm-scaler/vLLM env overrides after sourcing the promoted MiniMax env. This prevents sweeps from silently reverting to promoted defaults.
- Added benchmark log lines for the active MoE/logits/allreduce/QK helper toggles.
- Repeated known-good CCL run:
  - log: `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260531T183538Z.log`
  - elapsed: `17.357 s`
  - total throughput: `117.99 tokens/s`
  - output throughput: `88.49 tokens/s`
- Fresh-cache PIECEWISE runs initially failed because static-shape piecewise subgraphs compiled both `(1, 1)` and `(1, 512)` entries, then asserted that only one compiled entry could exist.
- Patched `vllm/compilation/piecewise_backend.py` so static-shape subgraphs with multiple compiled entries select the unique single-size entry and still assert if that choice is ambiguous.
- Fresh-cache default now starts and completes:
  - cold fresh-cache run: `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260531T185024Z.log`, `55.28 output tok/s`
  - warm rerun on that cache: `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260531T185454Z.log`, `85.97 output tok/s`
  - original warmed cache after patch: `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260531T185633Z.log`, `88.17 output tok/s`
- `VLLM_XPU_USE_LLM_SCALER_MOE_WS=0` is not an easy win; with fresh cache it hits the same compile-range shape issue path and is not promoted.
- `--block-size 128` warm rerun: `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260531T190235Z.log`, `84.86 output tok/s`; reject.
- `--block-size 512` warm rerun: `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260531T190837Z.log`, `85.21 output tok/s`; reject.
- `VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP=0` warm rerun: `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260531T192144Z.log`, `72.84 output tok/s`; reject.
- `VLLM_MINIMAX_MOE_OUTPUT_ALLREDUCE_INSIDE_CUSTOM_OP=0` warm rerun: `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260531T192757Z.log`, `85.34 output tok/s`; reject.
- `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP=0` warm rerun: `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260531T193416Z.log`, `88.17 output tok/s`; neutral/no promotion over default.
- `FULL_DECODE_ONLY` fails with the piecewise compile-range assertion.
- `FULL_AND_PIECEWISE` fails on B70 full graph capture with `The sycl_ext_oneapi_work_group_scratch_memory feature is not yet available for use with the SYCL Graph extension.`
- Post-patch CCL semantic canary passed:
  - file: `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/quality-smoke-20260531T191426Z.json`
  - result: `passed=true`, `1536` generated tokens across canary prompts, deterministic, no NUL/control/degenerate output

MiniMax logits path investigation:

- The 192-expert MiniMax logits and logits-WS kernels now load, but they are not promoted.
- Low-level synthetic tests showed separate top-k and monolithic MiniMax top-k agree for random `E=192,H=3072,I=1536,T=1` inputs within expected fp order differences.
- True eager runs with `VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS=1` are no longer token-zero corrupt; 64-token canaries produced nondegenerate text. They failed only because the model was still in the `think` section at 64 tokens.
- Graph runs with the logits path and default auto compile ranges fail with the same piecewise assertion as above.
- Adding `--disable-auto-compile-ranges` avoids that assertion for both non-WS and WS logits paths, but the 64-token graph canary only ran around `4.3 output tokens/s`, far below the conservative path.
- Keep `VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS=0` as the default. The logits path needs more integration work before it is worth benchmarking for records.

Greedy correction and local-argmax probes:

- Important correction: `vllm bench throughput` defaults to `temperature=1.0` unless `VLLM_BENCH_TEMPERATURE=0` is set. The earlier `88.49 output tok/s` REAP run is valid as a throughput datapoint, but the archived/submitted payload described it as temperature `0`.
- True greedy conservative CCL path:
  - command prefix: `CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK=0 VLLM_BENCH_TEMPERATURE=0`
  - first run: `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260531T214914Z.log`, `89.14 output tok/s`, `118.85 total tok/s`
  - repeat: `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260531T221003Z.log`, `89.19 output tok/s`, `118.92 total tok/s`
  - decision: new corrected REAP best.
- `VLLM_XPU_LOCAL_ARGMAX_DECODE=1` default pair path warmed to `75.13 output tok/s`; reject for REAP.
- `VLLM_XPU_LOCAL_ARGMAX_DECODE=1 VLLM_XPU_LOCAL_ARGMAX_DIRECT_GATHER_REUSE=1` warmed to `75.34 output tok/s`; reject for REAP.
- `VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS=1` with true greedy started after the piecewise fix but warmed to `72.44 output tok/s`; reject for REAP.

LocalMaxxing:

- REAP has now been submitted as a public baseline. The corrected best REAP result is `89.19 output tokens/s` on the true-greedy warmed conservative CCL path. It is quality-gated, but still only a modest baseline rather than a major record-class improvement over the existing MiniMax M2.7 production lane.
- User requested a LocalMaxxing update on 2026-05-31. A ready-to-submit payload was archived at `localmaxxing/reap-minimax-m27-autoround-ccloverride-p512n1536-20260531.payload.json` with queue file `localmaxxing/reap-minimax-m27-autoround-ccloverride-p512n1536-20260531.queue.json`.
- Submission attempt:
  - command: `/home/steve/.venvs/vllm-xpu/bin/python /home/steve/llm-optimizations/scripts/submit_localmaxxing_results.py --payloads ...queue.json --label reap-minimax-m27-autoround-ccloverride-p512n1536-20260531`
  - first result: not submitted, `LMX_API_KEY is required`
  - second result after user provided API key: HTTP `201`, status `APPROVED`
  - LocalMaxxing ID: `cmpub8nkx00pzmq01wjujveuj`
  - submit log: `localmaxxing/reap-minimax-m27-autoround-ccloverride-p512n1536-20260531.submit.log`
  - caveat: local payload notes said `temperature=0`, but the benchmark command did not set `VLLM_BENCH_TEMPERATURE=0`; treat this row as a sampled/default-temperature throughput datapoint, not the corrected greedy row.
- Corrected true-greedy REAP payload:
  - payload: `localmaxxing/reap-minimax-m27-autoround-greedy-ccloverride-p512n1536-20260531.payload.json`
  - queue: `localmaxxing/reap-minimax-m27-autoround-greedy-ccloverride-p512n1536-20260531.queue.json`
  - command includes `VLLM_BENCH_TEMPERATURE=0`
  - result: HTTP `201`, status `APPROVED`
  - LocalMaxxing ID: `cmpuc7tkq00qamq01z61pnb3c`
  - submit log: `localmaxxing/reap-minimax-m27-autoround-greedy-ccloverride-p512n1536-20260531.submit.log`

CCL IPC promotion:

- `CCL_IPC=pidfd` plus explicit `CCL_ZE_IPC_EXCHANGE=pidfd` is a small REAP win when combined with `CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK=0`.
- Same-window screen:
  - `pidfd`: `89.42738863012866 output tok/s`
  - `pidfd` repeat: `89.32689830491869 output tok/s`
  - default IPC control: `89.27580338562741 output tok/s`
  - `sockets`: `88.90492979756878 output tok/s`; reject
- Promoted config run:
  - log: `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260531T232017Z.log`
  - JSON: `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260531T232017Z.json`
  - elapsed: `17.16216013500525 s`
  - total throughput: `119.3322975598359 tok/s`
  - output throughput: `89.49922316987691 tok/s`
- Explicit `pidfd` quality smoke passed:
  - file: `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/quality-smoke-20260531T231727Z.json`
  - `passed=true`, deterministic, no NUL/control/degenerate output
- REAP defaults now set `CCL_IPC=pidfd`, `CCL_ZE_IPC_EXCHANGE=pidfd`, and `CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK=0`.
  The quality and serve wrappers now translate `CCL_IPC`; the benchmark wrapper logs `ccl_ipc` and `ccl_ze_ipc_exchange`.
- LocalMaxxing update:
  - payload: `localmaxxing/reap-minimax-m27-autoround-greedy-pidfd-p512n1536-20260531.payload.json`
  - queue: `localmaxxing/reap-minimax-m27-autoround-greedy-pidfd-p512n1536-20260531.queue.json`
  - result: HTTP `201`, status `APPROVED`
  - LocalMaxxing ID: `cmpuesbma00r5mq01yk0zdcjx`
  - submit log: `localmaxxing/reap-minimax-m27-autoround-greedy-pidfd-p512n1536-20260531.submit.log`

## 2026-06-01

- Added a REAP profile wrapper and log-summary parser for timing diagnostics.
- Extended the REAP wrapper to preserve more MiniMax override flags during
  screens.
- Important cache lesson: a temporary source-level instrumentation pass caused
  vLLM to recompile and overwrite the AOT artifact in the promoted REAP cache
  root. Afterward, the same no-logits-WS path direct-loaded but ran around
  `85.6-85.9 output tok/s`, below the archived `89.49922316987691 output tok/s`.
- Rejected warmed screens:
  - `VLLM_MINIMAX_M2_ATTN_DELAY_ALLREDUCE=1`: about `85.7 output tok/s`
  - `VLLM_MINIMAX_MOE_DELAY_ALLREDUCE=1`: about `85.4 output tok/s`
  - `MAX_BATCHED_TOKENS=1024`: about `80.3 output tok/s`
  - logits WS plus skip redundant contiguous: about `87.0 output tok/s`
- Logits WS retest reached about `87.3 output tok/s`, faster than the rebuilt
  conservative cache but still below the archived best.
- Logits WS plus cached op was about tied at `87.3 output tok/s`, but the quality
  smoke failed during engine startup with
  `'MiniMaxText01RMSNormTP' object has no attribute '_minimax_clean_weight_xpu'`.
- No new LocalMaxxing submission and no promoted runtime change.

89.5 repro audit:

- Exact rerun of the archived best settings from the current promoted cache root
  landed at `85.68 output tok/s`:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T030742Z.log`.
- The archived `89.49922316987691 output tok/s` run used backbone key
  `f728d2c0cf`; current direct reruns choose `4258951ecd`. Cache metadata shows
  env/config/compiler hashes match and only `code_hash` differs.
- Forcing `f728d2c0cf` against the current no-logits root fails with
  `ValueError: not enough values to unpack (expected 812, got 749)`, confirming
  the current AOT payload no longer matches the archived backbone.
- A preserved root,
  `/mnt/fast-ai/vllm-cache-exp/minimax-m27-reap-sweep-moe-full-forward0-20260531T193000Z`,
  still runs the async benchmark with explicit `cache_dir=f728d2c0cf`:
  - `88.94 output tok/s`, `118.58 total tok/s`:
    `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T031504Z.log`
  - repeat `88.76 output tok/s`, `118.35 total tok/s`:
    `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T031949Z.log`
- The recovered path is not promoted: the sync quality harness, now able to
  target an explicit compile cache dir, fails on the preserved AOT pair with
  `'MiniMaxText01RMSNormTP' object has no attribute '_minimax_clean_weight_xpu'`.

Clean-weight quality follow-up:

- Tried an experimental vLLM patch to mirror MiniMax q/k RMSNorm clean-weight
  tensors from the weight parameter onto the owning norm module during weight
  load. Patch archived at
  `patches/vllm-minimax-clean-weight-owner-experiment.patch`.
- The patch fixed the sync quality startup failure on a fresh cache; a repeat
  strict quality smoke passed:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/quality-smoke-20260601T035827Z.json`,
  `combined_token_sha256=f97fdf040fb42b7597cab517888d9bf0309aba0a29d0c92249287c10c91df14e`.
- The patch is not promoted because source-hash changes forced new AOT builds
  with materially worse decode rates:
  - patched default fresh cache: `80.47 output tok/s`,
    `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T040006Z.log`
  - patched `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP=0`: `54.17 output tok/s`,
    `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T040648Z.log`
  - patched `VLLM_MINIMAX_POST_ATTN_NORM_MOE_CUSTOM_OP=1`: `49.19 output tok/s`,
    `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T041236Z.log`
- Live vLLM source was reverted to the pre-experiment state after recording the
  patch.
- Preserved fast-cache check after the revert:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T041712Z.log`
  direct-loaded `f728d2c0cf` and reached `88.40 output tok/s`, `117.87 total tok/s`.
- Decision: keep using the preserved `f728d2c0cf` lane only as a recovery/debug
  reference. It is close to the archived best but still lacks a current sync
  quality pass on the exact stale AOT pair.

OpenAI serve quality fix:

- `vllm serve` was producing token id `0` / NUL output even when eager and with
  parsers disabled. A logprobs probe exposed NaN logits, so the issue was below
  response parsing.
- A `SamplingParams.skip_clone` deep-copy probe did not fix the issue and was
  reverted from live vLLM source.
- Root cause was a stale serve-env bundle inherited from the older MiniMax lane.
  `serve.sh` now mirrors the passing quality harness by default:
  - `VLLM_MINIMAX_M2_ATTN_DELAY_ALLREDUCE=1`
  - `VLLM_MINIMAX_QK_RMS_XPU_HELPER=0`
  - `VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT=0`
- Eager OpenAI quality pass:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/openai-quality-smoke-qualityenv-eager-ml2048-20260601T050148Z.json`.
- Compiled 32K OpenAI quality pass:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/openai-quality-smoke-qualityenv-graph-ml32768-20260601T050633Z.json`.
- New compiled serve cache:
  - backbone key `b234935ae7`
  - AOT `c6b129b47a7bce6e1ac7bb116707a25b30df10f84ae3be4497d3f4c95e1b992f`
- Endpoint p512/n1536 two-repeat benchmark on the quality-clean compiled server:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/openai-endpoint-qualityenv-graph-p512n1536-r2-20260601T050839Z.json`
  - `82.05` mean output tok/s after first chunk
  - `107.15` mean total tok/s
  - `393.17 ms` mean client TTFT
- Decision: quality-clean OpenAI serve path is now established but not speed
  promoted. Next step is one-at-a-time ablation of the three serve-env toggles
  to recover decode rate without reintroducing NaN logits.

OpenAI serve ablation:

- Added corrected endpoint measurement for streaming chunk cadence:
  `scripts/measure-openai-endpoint-metrics.py` now reports
  `tok_s_out_client_after_first_chunk_corrected`, subtracting the estimated
  first streamed chunk tokens from the post-first-chunk numerator.
- `VLLM_MINIMAX_QK_RMS_XPU_HELPER=1` passed the 32K compiled OpenAI quality smoke
  and improved endpoint p512/n1536 decode:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/openai-endpoint-qkhelper1-graph-p512n1536-r2-20260601T051723Z.json`
  - mean output tok/s after first chunk: `82.6854`
  - mean total tok/s: `107.8990`
  - logprobs probe returned HTTP `200`, so the previous NaN-logits symptom did
    not recur.
- `VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT=1` is not graph-safe:
  - eager 2K quality passed:
    `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/openai-quality-smoke-restore1-eager-ml2048-20260601T052041Z.json`
  - compiled 32K quality failed with all-NUL output:
    `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/openai-quality-smoke-restore1-graph-ml32768-20260601T052241Z.json`
- `VLLM_MINIMAX_M2_ATTN_DELAY_ALLREDUCE=0` was quality-clean but slower:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/openai-endpoint-attndelay0-graph-p512n1536-r2-20260601T052446Z.json`,
  `82.3183` mean output tok/s.
- qk-helper plus `ATTN_DELAY_ALLREDUCE=0` also did not beat qk-helper alone:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/openai-endpoint-qkhelper1-attndelay0-graph-p512n1536-r2-20260601T052801Z.json`,
  `82.4583` mean output tok/s.
- Reducing OpenAI serve max context to 2K did not recover the offline record:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/openai-endpoint-qkhelper1-graph-ml2048-p512n1536-r2-20260601T053411Z.json`,
  `82.1484` mean output tok/s.
- Streaming cadence screen:
  - qk-helper plus `--stream-interval 8` passed quality and reached
    `82.7617` old output tok/s, `82.7078` corrected output tok/s, `107.9963`
    total tok/s:
    `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/openai-endpoint-qkhelper1-streamint8-graph-p512n1536-r2-20260601T053846Z.json`
  - qk-helper plus `--stream-interval 16` regressed to `82.6162` corrected
    output tok/s:
    `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/openai-endpoint-qkhelper1-streamint16-graph-p512n1536-r2-20260601T054153Z.json`
- Serve wrapper decision:
  - promote qk-helper default to `VLLM_MINIMAX_QK_RMS_XPU_HELPER=1`
  - keep restore-weight off
  - keep delayed attention allreduce on
  - add `VLLM_STREAM_INTERVAL` as an opt-in serve wrapper knob; `8` is a small
    endpoint win but changes client-visible streaming cadence.

Restore-off and output-path audit:

- User correctly flagged `82.7078` as worse than the archived
  `89.49922316987691 output tok/s` REAP record. Treat it as an endpoint
  diagnostic, not a promotion candidate.
- Found and fixed a benchmark-wrapper bug: `bench-decode.sh` was not preserving
  `VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT` or
  `VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT_MIN_TOKENS` after sourcing the older
  MiniMax promoted env. The earlier "restore-off" direct `85.x` result was
  actually still restore-weight-on.
- Endpoint prompt/log-stat follow-up did not recover throughput:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/openai-endpoint-qkhelper1-disablelogstats-vllmrandom-graph-p512n1536-r2-20260601T123011Z.json`,
  `82.39036990907539` corrected output tok/s, `107.49263424479153` total
  tok/s.
- The preserved fast `f728d2c0cf` cache does not boot under the current
  OpenAI-server path; startup fails with `ValueError: not enough values to
  unpack (expected 811, got 749)`.
- True restore-off direct run after the wrapper fix:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T124258Z.json`,
  `53.151145192997` output tok/s on the first request after a fresh compile.
- Warmed restore-off direct repeat:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T124723Z.json`,
  `80.62106717066092` output tok/s, `107.49475622754791` total tok/s.
- Restore-weight with `VLLM_MINIMAX_QK_NORM_COMPILE_USE_PARAM=1` still failed
  the compiled 32K OpenAI quality smoke with all-NUL output:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/openai-quality-smoke-restore1-param1-graph-ml32768-20260601T125336Z.json`.
- Restore-weight with qk-helper disabled also failed the compiled 2K OpenAI
  quality smoke with the same all-NUL output:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/openai-quality-smoke-restore1-qk0-graph-ml2048-20260601T130428Z.json`.
  This points at the restore-weight graph path itself rather than the qk-helper
  custom op.
- Finite tracing of the same restore-weight/qk-helper-off compiled 2K server
  narrowed the all-NUL failure to the final attention block:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/restore1-qk0-layer-boundary-trace-20260601T130915Z.jsonl`.
  Layers 58-60 and `minimax.layer61.input` remained finite. The first bad
  tensor was `minimax.layer61.after_attn`; the final hidden state,
  `sample_hidden_states`, and all `200064` logits were then all-NaN. Next source
  target: graph-captured layer 61 attention under
  `VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT=1`.
- Added `bench-async-output-kind.py` for direct async `RequestOutputKind`
  comparisons. A diagnostic restore-off/logits-WS run showed all output kinds in
  the same low-80s band, so output-kind selection is not the main limiter:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/direct-async-outputkind-qkhelper1-restore0-p512n1536-20260601T125504Z.json`.
- Decision: no new LocalMaxxing submission and no runtime promotion from this
  pass. Keep qk-helper, restore-weight off, delayed attention allreduce on for
  OpenAI serve. The next meaningful speed target is source work on
  restore-weight graph safety or another model-forward/MoE fusion path.

Restore-weight param fallback experiment:

- Layer 61 attention/QK traces narrowed the restore-weight all-NUL failure to
  K-side QK norm. `qkv`, Q/K variance, and `q_after_qk_norm` were finite, while
  `k_after_qk_norm` contained NaNs/infs before attention:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/restore1-qk0-layer61-qknorm-trace-20260601T131616Z.jsonl`.
- Archived patch:
  `experiments/minimax-m27-reap-autoround-vllm/patches/vllm-minimax-qk-restore-prefer-param-experiment.patch`.
  It makes restore-weight prefer the live parameter when sane and use the CPU
  clean copy only to repair corrupt parameters.
- The patch fixed restore-weight OpenAI quality:
  - qk-helper off quality passed:
    `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/openai-quality-smoke-restore1-paramweightfix-qk0-graph-ml2048-20260601T132305Z.json`
  - qk-helper on quality passed:
    `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/openai-quality-smoke-restore1-paramweightfix-qk1-graph-ml2048-20260601T132945Z.json`
- Throughput did not recover:
  - qk-helper off endpoint corrected output `82.22418078631115` tok/s:
    `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/openai-endpoint-restore1-paramweightfix-qk0-graph-ml2048-p512n1536-r2-20260601T132432Z.json`
  - qk-helper on endpoint corrected output `81.94737970396619` tok/s:
    `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/openai-endpoint-restore1-paramweightfix-qk1-graph-ml2048-p512n1536-r2-20260601T133115Z.json`
  - warmed direct qk-helper-off total `106.86224461653275` tok/s, about `80.15`
    output-equivalent tok/s:
    `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T133722Z.json`
- Decision: patch is not speed-promoted. Restore live vLLM source to the
  pre-experiment behavior before continuing speed work; keep the patch and trace
  as correctness evidence.

Async quality and logits-WS follow-up:

- Added `experiments/minimax-m27-reap-autoround-vllm/scripts/async-quality-smoke.py`
  to validate the same async-engine path used by direct async throughput runs.
- Preserved fast `f728d2c0cf` still benchmarks well:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T134739Z.log`,
  `118.61` total tok/s, `88.96` output tok/s. The new async quality smoke
  rejected it with all token-id `0` output:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-f728-fast-20260601T135246Z.json`.
- Existing logits-WS fast cache `4258951ecd` also failed async quality with all
  token-id `0` output:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-logitsws-425895-20260601T135551Z.json`.
- Fresh quality-safe logits-WS with restore off and attention-delay on passed
  async quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-logitsws-qualitysafe-20260601T135722Z.json`,
  but decoded only `108.34` total tok/s, `81.26` output tok/s:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T140120Z.log`.
- Fresh logits-WS with restore off and attention-delay off also passed async
  quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-logitsws-restore0-attndelay0-20260601T140312Z.json`,
  but decoded only `107.86` total tok/s, `80.89` output tok/s:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T140720Z.log`.
- Decision: reject throughput-only caches that fail async quality. Do not
  promote logits-WS yet; quality-safe logits-WS is slower than the current
  OpenAI qk-helper lane. `82.7078` remains a regression versus the archived
  throughput-only result and is not a LocalMaxxing candidate.

f728 quality and speed split:

- Added runtime-only diagnostic shim:
  `experiments/minimax-m27-reap-autoround-vllm/scripts/sitecustomize_minimax_clean_weight/sitecustomize.py`.
  It mirrors MiniMax q/k RMSNorm clean weights from the loaded `Parameter` onto
  the owning `MiniMaxText01RMSNormTP` module without editing live vLLM source.
- Fresh `FULL_FORWARD_CUSTOM_OP=0`, restore off, qk-helper on passed async
  quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-fullforward0-restore0-qksafe-20260601T1828.json`,
  then decoded `83.52 output tok/s`, `111.36 total tok/s`:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T223035Z.json`.
- Fresh `FULL_FORWARD_CUSTOM_OP=0`, restore off, attention-delay off passed
  async quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-fullforward0-restore0-attndelay0-20260601T1834.json`,
  then decoded `83.13 output tok/s`, `110.84 total tok/s`:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T223723Z.json`.
- Preserved `f728d2c0cf` without the shim still direct-loaded and decoded at
  `88.63 output tok/s`, `118.17 total tok/s`:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T224417Z.json`,
  but async quality failed with all `384` generated tokens equal to token id `0`
  and NUL/control output:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-f728-no-shim-control-20260601T1846.json`.
- The exact same preserved `f728d2c0cf` cache with the runtime owner-clean-weight
  shim passed async quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-f728-sitecustomize-owner-restore1-20260601T1842.json`,
  but decoded only `83.32 output tok/s`, `111.09 total tok/s`:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T224156Z.json`.
- Graph counts explain why this is not just a missing MoE-inline issue:
  preserved fast REAP and old non-REAP have `fused_moe=124`,
  `minimax_m2_moe_forward=0`, `_minimax_clean_weight_xpu=992`, and
  `all_reduce=813`; fresh quality-safe restore-off paths still inline MoE
  (`fused_moe=124`, `minimax_m2_moe_forward=0`) but remove the clean-weight attr
  references and land in the low-83 band.
- Decision: the current `88.x` preserved `f728d2c0cf` lane is throughput-only
  corrupt unless repaired, and the repair currently costs the speed back down to
  about `83.3` output tok/s. Do not promote or submit. Next sizeable improvement
  requires source work in Q/K RMS restore graph safety or a deeper MoE/QK fusion,
  not more env/cache sweeps.

Candidate-router repair screen:

- Tried `VLLM_MINIMAX_M2_CANDIDATE_ROUTER_TOPM=16` with exact XPU repair on the
  quality-safe restore-off path.
- First attempt failed graph capture because
  `moe_int4_ops::minimax_m2_candidate_repair_topk` had no fake/meta
  implementation for TorchDynamo.
- Archived compile-enablement patch:
  `patches/vllm-minimax-candidate-router-fake-20260601.patch`.
- With that fake registration applied, async quality passed:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-candidate-router-top16-fake-restore0-20260601T2304.json`,
  `384` generated tokens, `177` distinct generated token IDs, no NUL/control
  output.
- Warm p512/n1536 benchmark did not improve:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T230739Z.json`,
  `18.422281710983953 s`, `111.16972545148504` total tok/s, about `83.38`
  output tok/s.
- Decision: reject as a speed path and remove the live vLLM patch to avoid
  unnecessary code-hash churn. Keep the patch archived only for future candidate
  router work.

Old-fast retest and live-K rejects:

- Current quality-valid REAP best remains the fresh restore-off, qk-helper,
  attention-delay-on path:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T223035Z.json`,
  `83.517837` output tok/s and `111.35711559954889` total tok/s.
- Same-checkout non-REAP control is also in the low-83 band:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode-nonreap/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T231613Z.json`,
  `83.050037` output tok/s and `110.73338297867303` total tok/s.
- `FULL_FORWARD_CUSTOM_OP=1`, restore off, qk-helper on passed async quality but
  decoded only `59.114708` output tok/s:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode-fullforward1-restore0/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T000428Z.json`.
- Copied the old promoted cache root to
  `/mnt/fast-ai/vllm-cache-exp/minimax-m27-reap-autoround-no-logits-ws-20260531-retest-20260602T000854Z`
  and retested old settings. Quality passed after rebuild:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/quality-smoke-20260602T000919Z.json`,
  but throughput fell to `62.060616` output tok/s:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode-oldfast-retest/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T001254Z.json`.
- Graph comparison: old `f728d2c0cf` traces per-layer gate weights plus
  generic `torch.ops.vllm.moe_forward`; rebuilt old settings generated
  `fd410802e8`, which calls `torch.ops.vllm.minimax_m2_moe_forward` with encoded
  layer names. The cache env/config/compiler hashes match and the source
  code hash differs, so the old speed cannot be recovered by env settings alone.
- Rejected live-K selector screens:
  - global live-K hung and was killed
  - layer-61 live-K with qk-helper off passed quality but decoded about
    `57.43` output tok/s
  - layer-61 live-K against preserved `f728` with qk-helper on passed quality
    but decoded about `60.43` output tok/s
- Removed the rejected live-K selector from active vLLM source and archived it
  only as `patches/vllm-minimax-qk-live-k-layer-selector-20260601.patch`.
- Full notes:
  `notes/2026-06-01-oldfast-retest-and-livek-rejects.md`.

2026-06-02 easy-win screens:

- Extended the REAP wrappers/quality harness to preserve and record newer
  low-level knobs, including FP16 router, QKV narrow split, Q/K direct scale,
  pre-capture sanitizer, and static PIECEWISE entry policy.
- Added `--enforce-eager` to `scripts/async-quality-smoke.py` for audit-only
  runs outside Dynamo graph capture.
- `VLLM_MINIMAX_QKV_NARROW_SPLIT=1` passed async quality but decoded only
  `83.21` output tok/s:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T025506Z.log`.
- FP16 router passed eager audit with zero expert-set mismatches and zero
  candidate misses, but had eight ordered-only decode mismatches. Compiled
  quality passed and benchmarked at `84.11` output tok/s:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T030623Z.log`.
- Built and installed the missing `minimax_qk_rms_xpu` helper with oneAPI
  `icpx`; active-helper quality passed, but throughput regressed to `82.29`
  output tok/s:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T031520Z.log`.
- Pre-capture Q/K norm sanitizer quality passed but benchmarked at `83.10`
  output tok/s; static PIECEWISE `widest` passed quality but regressed to
  `81.12` output tok/s.
- Decision: do not submit a LocalMaxxing update. Conservative quality-safe best
  remains `83.517837` output tok/s; FP16 router is an opt-in candidate at
  `84.11` output tok/s but is not a conservative promotion.
- Full notes:
  `notes/2026-06-02-easy-win-screens.md`.

MoE microbench and logits-WS retest:

- Added `scripts/bench-reap-moe-micro.py` for the REAP per-rank MoE shape
  (`hidden=3072`, `intermediate=384`, `experts=192`, `top_k=8`).
- Extended benchmark/quality metadata and env passthrough for MoE WS tile,
  top-k-weight precision, and scratch-buffer reuse flags.
- Synthetic default microbench showed the workspace paths materially faster
  than raw routed U4 at decode-like sizes; `tokens=1` default measured
  `routed_ws=0.0870 ms`, `minimax_logits_ws=0.0881 ms`, and
  `routed_u4=0.1663 ms`.
- `VLLM_XPU_MOE_WS_DOWN_HTILE=4` passed async quality but decoded only `83.56`
  output tok/s:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T033622Z.log`.
- Logits WS with down tile 4 passed async quality and decoded `84.35` output
  tok/s:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T034250Z.log`.
- Logits WS with default tiles passed async quality and is the best new
  live-source candidate from this pass:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T035955Z.log`,
  `85.10` output tok/s and `113.46` total tok/s.
- Reused intermediates passed quality but decoded `84.43` output tok/s; reject.
- FP16 top-k weights looked good in the synthetic microbench but decoded only
  `84.29` output tok/s and changes top-k-weight precision; reject.
- Decision: default logits WS is the current fresh-cache/live-source candidate,
  but it is still below the archived `89.49922316987691` output tok/s REAP
  result, so no LocalMaxxing submission from this pass.
- Full notes:
  `notes/2026-06-02-moe-micro-and-logitsws-retest.md`.

Profile/output-reuse/cache-op follow-up:

- Rebuilt the llm-scaler INT4 MoE extension with `setup_moe_int4_only.py
  build_ext --inplace`; the one-op BMG build succeeded and installed a `97M`
  `moe_int4_ops` shared object.
- Corrected baseline rerun after the rebuild, with logits-WS, restore off,
  qk-helper off, attention-delay on, and `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP=0`:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T125056Z.log`,
  `85.21` output tok/s and `113.61` total tok/s.
- `VLLM_XPU_LLM_SCALER_MOE_CACHE_MINIMAX_LOGITS_OP=1` was retested under the
  corrected restore-off/full-forward-off settings. Quality passed, but decode
  regressed to `84.64` output tok/s:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T125738Z.log`.
- Archived a llm-scaler source patch for output-buffer reuse in the MiniMax WS
  path:
  `patches/llm-scaler-minimax-ws-output-reuse-experiment-20260602.patch`.
  It is default-off behind `VLLM_XPU_MINIMAX_WS_REUSE_INTERMEDIATES`.
- Corrected output-reuse quality passed under the accepted full-forward-off
  settings, but decode regressed to `84.93` output tok/s:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T130101Z.log`.
- Decision: reject cached-op and output-reuse experiments. Keep the current
  live-source best at `85.21` output tok/s. No new LocalMaxxing submission.
- Full notes:
  `notes/2026-06-02-profile-output-reuse-cacheop-followup.md`.

U4 signed-compact specialization rejection:

- Specialized `moe_ws_up_routed_cutlass_int4_kernel` and
  `moe_ws_down_cutlass_int4_kernel` on `signed_compact` so the hot decode branch
  became `if constexpr (SignedCompact)`.
- Archived the tested source shape as a compact patch excerpt:
  `patches/llm-scaler-ws-signedcompact-specialization-rejected-20260602.patch`.
- The one-op BMG build succeeded, but the installed `moe_int4_ops` shared object
  grew from `97M` to `115M`.
- Quality passed:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-u4specialized-logitsws-qk0-20260602T131747Z.json`.
- Decode regressed to `80.00686771866597` output tok/s and
  `106.67582362488797` total tok/s:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode-u4specialized/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T132219Z.log`.
- Reverted the specialization in active llm-scaler source and rebuilt the
  extension. The installed shared object returned to `97M`, import passed, and
  no `SignedCompact` symbols remain in `csrc/moe_batch/moe_int4.sycl`.
- Restore async quality passed on a fresh cache:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-restored-u4runtime-logitsws-qk0-20260602T1330.json`,
  `384` generated tokens, `179` distinct generated token IDs, no NUL/control
  output.
- Restore decode on the same cache measured `84.229293276551` output tok/s and
  `112.30572436873467` total tok/s:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode-restored-u4runtime/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T133537Z.log`.
- Decision: reject and keep the runtime branch path. The branch was not the
  meaningful bottleneck, and the larger specialized binary likely hurt more than
  it helped. No LocalMaxxing submission.
- Full notes:
  `notes/2026-06-02-u4-specialization-reject.md`.
