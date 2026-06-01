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
