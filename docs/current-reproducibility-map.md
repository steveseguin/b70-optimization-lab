# Current Reproducibility Map

This page connects the active Gemma 4 service, the deployable MiniMax baseline,
the session-cache experiments, the TurboQuant patch, and the long-context
research path. It is meant for a fresh human or agent who needs to reproduce or
review the current work without reading every historical note first.

Hardware scope: the local Intel lab is four Arc Pro B70 32 GB GPUs
(`128 GB` aggregate VRAM). Results here are useful because they are produced on
real community-accessible XPU hardware, but the same limit also constrains
larger model coverage. Additional high-VRAM Intel hardware would let this map
include larger GLM/DeepSeek-class lanes and more concurrent service/optimization
comparisons without sacrificing the current endpoint. The lab has spare EPYC
9015 PCIe 5.0 slot capacity, so the missing piece for broader Intel coverage is
higher-memory XPU hardware rather than host expansion.

## What Is Production Today

The active LAN endpoint on this host is the Gemma 4 c8 model-slot profile:

- model: `Intel/gemma-4-12B-it-int4-AutoRound`
- local model path used in the lab: `/mnt/fast-ai/llm-models/gemma4-12b-it-int4-autoround-intel`
- hardware: 4x Intel Arc Pro B70 32GB
- engine: vLLM/XPU TP4
- endpoint: OpenAI-compatible API on `0.0.0.0:8000`
- served context: `32768`
- max active generations: `8`
- prefix caching: enabled
- modalities: text and image
- auth: none

Restore production Gemma 4 c8:

```bash
cd /home/steve/llm-optimizations
printf '%s\n' "/'" | sudo -S -p '' \
  scripts/switch-vllm-model-slot.sh switch gemma4-12b-it-int4-autoround-c8
```

Current Gemma 4 recipe and results:

- `../experiments/gemma4-12b-int4-autoround-vllm/README.md`
- `../experiments/gemma4-12b-int4-autoround-vllm/results-20260607-c10-c12-32k-boundary.json`
- `model-slot-switching.md`

Latest full-32K concurrency conclusion:

- Keep c8 as production for website-sized requests that need the 32K window.
- c10 is research-only: short prompts improved in aggregate, but near-32K
  throughput did not improve and TTFT worsened.
- c12 is rejected after Level Zero out-of-resources/device-lost under burst
  load.
- Prefix caching is useful for fixed system/project prefixes plus unique user
  content. In the half-shared synthetic test, c8 near-32K TTFT improved from
  about `22.20 s` to `12.45 s`.

## MiniMax Deployable Baseline

The MiniMax 32K FP16-family KV c1 endpoint remains the deployable baseline
recipe and optimization reference:

- model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- local model path used in the lab: `/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround`
- hardware: 4x Intel Arc Pro B70 32GB
- engine: vLLM/XPU TP4
- endpoint: OpenAI-compatible API on `0.0.0.0:8000`
- served context: `32768`
- max active generations: `1`
- default KV: `auto` / FP16-family

Fresh install guide:

`../repro/minimax-m27-b70-110tps-ubuntu24-20260523/README.md`

Human deployment guide:

`b70-minimax-ubuntu24-deployment.md`

Main server script:

`../repro/minimax-m27-b70-110tps-ubuntu24-20260523/scripts/06-serve-openai-compatible.sh`

Operational profile switcher:

`../experiments/minimax_xpu_kv_offload/scripts/switch_session_cache_profile.sh`

Restore c1:

```bash
cd /home/steve/llm-optimizations
experiments/minimax_xpu_kv_offload/scripts/switch_session_cache_profile.sh c1
```

Check status:

```bash
experiments/minimax_xpu_kv_offload/scripts/session_cache_status.sh
```

## Gemma 4 26B Realistic-Suite Observation

The current Gemma 4 26B A4B Q8 single-B70 realistic-suite observation is
documented in the result packet:

`../results/gemma4-26b-a4b-q8-b70/reproduce.md`

Use it when the goal is to reproduce the current fixed-suite cold-response
frontier rather than the older synthetic filled-long diagnostics. The older
standalone
`../repro/gemma4-26b-a4b-q8-b70-95tps-20260624/README.md` folder remains as a
superseded `95.264 tok/s` reproduction artifact.

Record identity:

- model: `unsloth/gemma-4-26B-A4B-it-GGUF`, `UD-Q8_K_XL` target
- draft: local `Q4_0` Gemma MTP draft only
- hardware: headless Supermicro AMD Threadripper PRO 5955WX platform, 128 GB
  DDR4, one Intel Arc Pro B70 32 GB used for the measured replica
- result: best strict result `123.67689864739785 tok/s` median
  generated-token throughput for tokens 1-100 after TTFT across the fixed
  realistic cold prompt suite, `cached_tokens=0` on every prompt,
  `realistic_final_gate.passed=true`.
  Evidence:
  `../data/gemma4-q8-gpu0-finalpostnorm-on-full512-20260630T024027Z-finalpost-full512/summary.json`.
  Config: llama.cpp `c926ad098`, reordered-Q8 VDR2, `FLASH_ATTN=on`,
  `CTX_SIZE=32768`, `GGML_SYCL_ENABLE_VMM=1`, `n_max=3`, `n_min=2`,
  `p_min=0.0475`, `UBATCH_SIZE=1024`,
  `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`,
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`,
  `LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1`,
  `--ctx-checkpoints 0`, no n-gram/history acceleration.
  This is the current submitted VDR2 selected-down fused weighted-sum plus
  FA-on 32K/VMM plus final post-norm residual fusion row, approved under the
  realistic-suite policy as `cmr01nnet000mld01x2tt6qds`. Same-family support
  includes the prior `121.41411987308553 tok/s` row
  (`cmqztiqdn02vnoe01egox6q3f`) and
  `../data/gemma4-q8-gpu2-baseline-recordconfirm-full512-20260629T225215Z/summary.json`
  at `119.94842631460949 tok/s`. Earlier selected-down rows
  `cmqyrpox4021dqk01co5o4fcw` and `cmqyo0jyt08ippk01vhiobdnm`, prior
  `98.34046474459183`, `95.82453787677183`, VDR2 `90-91`, and VDR4
  `87.61145306230438` submissions are superseded.
  The old `176.216232 tok/s` synthetic filled-long row remains diagnostic only
  and is not representative real-world throughput.
- primary artifacts:
  `../data/gemma4-q8-gpu0-finalpostnorm-on-full512-20260630T024027Z-finalpost-full512/summary.json`,
  `../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-final-postnorm-fusion-screen.md`,
  `../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-realistic-finalpostnorm-faon-vmm-ctx32768-full512-123tok-20260630.submit.log`,
  `../data/gemma4-q8-gpu1-selecteddown-bf16retest-control-full512-20260629T051323Z/summary.json`,
  `../results/gemma4-26b-a4b-q8-b70/20260629-vdr2-selected-down-record.md`,
  `../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-record-repeat-full512-variance.md`,
  `../data/gemma4-q8-gpu1-strict-vdr2-f16p021-bulksampled-confirm-B-n3-nmin2-p00475-ub1024-full512-20260628T052158Z/summary.json`,
  `../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T0245-crack100-runtime-sweeps.md`,
  `../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-mtp-n3-nmin2-p00475-ub1024-f16p021-bulksampled-full512-20260628.submit.log`,
  `../data/gemma4-q8-gpu1-strict-vdr2-f16p021-smallncols-full512-exactconfirm-n3-nmin2-p00475-ub1024-20260628T010121Z/summary.json`,
  `../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T0047-strict-f16p021-smallncols-record.md`,
  `../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-mtp-n3-nmin2-p00475-ub1024-f16p021-smallncols-full512-20260628.submit.log`,
  `../data/gemma4-q8-gpu1-strict-vdr2-recordconfirm-n3-nmin2-p00475-ub1024-20260627T221722Z/summary.json`,
  `../data/gemma4-q8-gpu2-strict-vdr2-n3-p00475-repeat-ub1024-v21-20260627T201757Z/summary.json`,
  `../data/gemma4-q8-gpu2-strict-vdr2-n3-p00475-ub1024-v19-20260627T191931Z/summary.json`,
  `../data/gemma4-q8-gpu0-strict-vdr2-repeat-n3-p005-ub1024-v19-20260627T191931Z/summary.json`,
  `../data/gemma4-q8-gpu0-strict-vdr2-n3-p005-ub1024-v18-20260627T191648Z/summary.json`,
  `../data/gemma4-q8-gpu1-strict-vdr2-th6-n3-p005-ub1024-v18-20260627T191648Z/summary.json`,
  `../data/gemma4-q8-gpu2-strict-vdr2-dth16-n3-p005-ub1024-v18-20260627T191648Z/summary.json`,
  `../data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-mtp-n3-nmin2-p00475-ub1024-v19-20260627.queue.json`,
  `../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-mtp-n3-nmin2-p00475-ub1024-v19-20260627.submit.log`,
  and
  `../repro/gemma4-26b-a4b-q8-b70/realistic-suite-v1.json`
- long-context service artifacts:
  `../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-dv512-gqa8-prefill-win.md`,
  `../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-long-context-prefill-service-gate.md`,
  `../repro/gemma4-26b-a4b-q8-b70/long-context-suite-v1.json`,
  `../scripts/bench-openai-long-context-suite.py`,
  `../repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh`, and
  `../repro/gemma4-26b-a4b-q8-b70/run-vdr2-short-decode-guard.sh`. The current
  validated service/prefill patch is
  `../patches/gemma4-26b-a4b-q8-b70/20260630-sycl-fattn-dv512-gqa8-ncols2.patch`
  with `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`. Use UB2048 as the balanced
  long-service setting, UB2304 for pure prefill, and keep UB1024 as the
  short-record reproduction setting. The KV-max mask pre-scan threshold
  diagnostic is preserved at
  `../patches/gemma4-26b-a4b-q8-b70/20260630-sycl-fattn-kv-max-scan-threshold.patch`
  and documented as a negative in
  `../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-kv-max-scan-threshold-negative.md`;
  do not disable the scan for this lane. The forced-`ncols1` diagnostic is
  preserved at
  `../patches/gemma4-26b-a4b-q8-b70/20260630-sycl-fattn-dv512-gqa8-ncols1-negative.patch`
  and documented as a negative in
  `../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-dv512-gqa8-ncols1-negative.md`;
  keep the GQA8 selector's implicit `ncols1=2` path. The `nbatch_fa=128`
  retune for the selected GQA8 FP16 tile is preserved at
  `../patches/gemma4-26b-a4b-q8-b70/20260630-sycl-fattn-dv512-gqa8-nbatchfa128-negative.patch`
  and documented as a negative/noise result in
  `../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-dv512-gqa8-nbatchfa128-negative.md`;
  keep the current `nbatch_fa=64` tile config. Phase-specific prompt/decode
  ubatch is preserved as a service candidate at
  `../patches/gemma4-26b-a4b-q8-b70/20260630-llama-phase-prefill-ubatch-memory-sized-experiment.patch`
  and documented in
  `../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-phase-prefill-ubatch-service.md`;
  the reproducible service wrapper is
  `../repro/gemma4-26b-a4b-q8-b70/run-vdr2-gqa8-phase-prefill-service.sh`.
  Use it for service/prefill validation only; short-decode headline submissions
  still use the fixed short record recipe and gate.
- source patch snapshot:
  `../patches/gemma4-26b-a4b-q8-b70/20260626T2225-llamacpp-gemma4-current-record-stack.patch`
  with note
  `../patches/gemma4-26b-a4b-q8-b70/20260626T2225-llamacpp-gemma4-current-record-stack.md`

The full optimization ledger remains in
`../results/gemma4-26b-a4b-q8-b70/README.md`.

## Baseline Build Inputs

The fresh Ubuntu 24 repro builds from source and applies two compressed patch
artifacts from the older strict-speed repro:

- `../repro/minimax-m27-b70-89tps-20260520/patches/vllm-active-promoted-minimax-89tps-20260520.patch.gz.b64`
- `../repro/minimax-m27-b70-89tps-20260520/patches/llm-scaler-active-promoted-minimax-89tps-20260520.patch.gz.b64`

The build script decodes and applies those patches automatically:

`../repro/minimax-m27-b70-110tps-ubuntu24-20260523/scripts/03-build-stack.sh`

Pinned source commits are listed in:

`../repro/minimax-m27-b70-110tps-ubuntu24-20260523/README.md`

Live-source audit snapshots from the originating machine are also tracked:

- `../patches/vllm-live-src-snapshot-20260525.patch`
- `../patches/llm-scaler-live-src-snapshot-20260525.patch`

These snapshots capture the dirty local `/home/steve/src/vllm` and
`/home/steve/src/llm-scaler` trees after the session-cache and TurboQuant
research. Treat them as review/audit artifacts, not as clean upstream-ready
patches. The clean fresh-install repro still uses the two compressed promoted
patch bundles listed above.

## Baseline Results

The fresh deployable baseline records:

- strict p512/n1536 comparable lane: `83.172` output tok/s, `110.896` total tok/s
- OpenAI endpoint warm decode: about `83.8-84.1` output tok/s
- prompt/prefill endpoint check: about `1.7k-1.8k` prompt tok/s
- served context: `32768`
- near-full context smoke: prompt `32408`, output `64`, no OOM

Tracked summaries:

- `../repro/minimax-m27-b70-110tps-ubuntu24-20260523/results/summary-20260523.json`
- `../repro/minimax-m27-b70-110tps-ubuntu24-20260523/results/context-window-32768-20260523.json`
- `../data/localmaxxing-minimax-m27-autoround-openai-32k-context-20260523.payload.json`
- `../data/localmaxxing-minimax-m27-autoround-openai-32k-endpoint-metrics-20260524.payload.json`

Detailed notes:

- `../notes/2026-05-23-b70-display-disable-32768-context.md`
- `../notes/2026-05-23-current-host-pcie4-prefill-check.md`

## Session-Cache / RAM-Backed Juggling

This is the main experimental path for keeping multiple long conversations
warm. It is not one huge active context.

Mental model:

- OpenAI-compatible requests are stateless.
- The client keeps and resends the full conversation history.
- vLLM hashes exact repeated token prefixes.
- CPU KV offload can park/reload those prefix KV blocks through system RAM.
- If old transcript text, system prompts, or chat templates change, prefix
  reuse can be lost after that point.

Entry points:

- `../experiments/minimax_xpu_kv_offload/REPRODUCE.md`
- `../experiments/minimax_xpu_kv_offload/ARTIFACTS.md`
- `../experiments/minimax_xpu_kv_offload/README.md`
- `../experiments/minimax_xpu_kv_offload/notes-20260525-session-cache-operations.md`

Scripts:

- `../scripts/install-minimax-vllm-service.sh`
- `../scripts/openai-lan-frontdoor.py`
- `../scripts/minimax-prod-health.py`
- `../scripts/minimax-prod-benchmark.py`
- `../deploy/systemd/minimax-vllm.service`
- `../deploy/systemd/minimax-openai-frontdoor.service`
- `../experiments/minimax_xpu_kv_offload/scripts/serve_session_cache.sh`
- `../experiments/minimax_xpu_kv_offload/scripts/switch_session_cache_profile.sh`
- `../experiments/minimax_xpu_kv_offload/scripts/session_cache_status.sh`
- `../experiments/minimax_xpu_kv_offload/scripts/session_cache_canary.py`

Current operational recommendation:

- c1 is production. Run it with `minimax-vllm.service` as a localhost backend
  on `127.0.0.1:18080` and `minimax-openai-frontdoor.service` as the no-auth
  LAN OpenAI-compatible endpoint on `0.0.0.0:8000`.
- Latest production-service near-32K LocalMaxxing result:
  `cmpm35jsa0003rt01zghtmwip` for prompt `32264`, output `64`,
  `63.91` output tok/s after TTFT, `1382.57` approximate prefill tok/s,
  `23.336 s` TTFT.
- c2 is the current known-good RAM-backed session-cache profile for two parked
  `32768`-token window sessions.
- c4 is the next target, but live service switching hit blockers.
- c8 is useful for smaller parked sessions but does not increase total decode
  throughput.

Near-full c2 validation:

- two concurrent strict-word sessions
- `32474` prompt tokens per session, `64948` combined prompt tokens
- expected first words matched the GPU-only baseline
- second-pass reload TTFT: `0.668-1.232 s`
- CPU-to-GPU KV reload: about `14-15 GB/s`

Known-good c2 operations smoke:

- two concurrent fact-word sessions
- `22540` prompt tokens per session
- exact output hashes matched across passes
- second-pass reload TTFT: `0.320-0.570 s`
- CPU-to-GPU KV reload: about `16.2 GB/s`

The operations smoke is intentionally smaller and cleaner. It does not define
the desired c2 context ceiling; c2 should be presented as a 32K-window profile.

Result file from the originating host:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/session-cache-c2-ops-fact-900lines-20260525T223527Z.json`

The raw `/mnt/fast-ai` file is not in GitHub; the result is summarized in:

`../experiments/minimax_xpu_kv_offload/notes-20260525-session-cache-operations.md`

Concurrency/sustained decode notes:

- `../experiments/minimax_xpu_kv_offload/notes-20260525-c2-session-cache-ladder.md`
- `../experiments/minimax_xpu_kv_offload/notes-20260525-c4-c8-session-cache-ladder.md`
- `../experiments/minimax_xpu_kv_offload/notes-20260525-sustained-concurrency-decode.md`

Headline sustained warm results:

- c4 at four `9234`-token prompts, `128` requested output tokens: about
  `109.76 tok/s` total warmed wall output
- c8 at eight `9234`-token prompts, `128` requested output tokens: about
  `110.34 tok/s` total warmed wall output
- c8 spreads roughly the same decode budget across more sessions; it does not
  double total throughput

Live c4 caveat:

- c4 started and reported `34304` GPU KV tokens
- a later operational smoke stalled on second-pass reload with waiting/deferred
  requests
- a rerun hit Level Zero `UR_RESULT_ERROR_DEVICE_LOST` while copying vLLM
  block-table state to GPU
- keep c4 experimental until this path is debugged

## TurboQuant

TurboQuant is a compressed-KV research lane. It can raise the live KV ceiling,
but it is not the production mode.

Patch artifact:

`../patches/vllm-turboquant-xpu-workspace-fallback-20260525.patch`

Repro script:

`../scripts/repro-minimax-turboquant-xpu-workspace-bug.sh`

Detailed notes:

- `../experiments/minimax_xpu_kv_offload/notes-20260525-c2-quality-and-turboquant.md`
- `../experiments/minimax_xpu_kv_offload/notes-20260525-turboquant-active-context-boundary.md`

Current status:

- the patch works around locked-workspace crashes in
  `turboquant_attn.py:_decode_attention` and `_continuation_prefill`
- `turboquant_k8v4` at 32K reported `80128` GPU KV tokens and `2.45x` max
  concurrency for a 32K request
- strict-word canaries passed at about `8K` and `32.5K` prompt tokens
- sustained decode around a `24874` token prompt was only about `16.5 tok/s`
  after TTFT
- `turboquant_4bit_nc` with `max_model_len=196608` reported `98304` GPU KV
  tokens but still could not serve a true 196K active request

Important boundary:

TurboQuant plus CPU KV offload still requires the active request's working KV
blocks to fit in live GPU memory. It helps capacity, but it is not active-context
overflow.

## Full 196K Active Context Path

The credible exact-quality path is CPU-paged attention, not simply increasing
`--kv-offloading-size`.

Design notes and probes:

- `../experiments/minimax_xpu_kv_offload/notes-20260525-cpu-paged-attention-design.md`
- `../experiments/minimax_xpu_kv_offload/notes-20260525-dense-staged-cpu-attention.md`
- `../experiments/minimax_xpu_kv_offload/notes-20260525-stagea-gpu-split-attention.md`
- `../experiments/minimax_xpu_kv_offload/probes/split_attention_merge_probe.py`
- `../experiments/minimax_xpu_kv_offload/probes/xpu_flash_attn_split_probe.py`
- `../experiments/minimax_xpu_kv_offload/probes/xpu_cpu_dense_staged_attention_probe.py`

Experimental patches:

- `../experiments/minimax_xpu_kv_offload/patches/kv-offload-admission-check-xpu-experiment-20260524.patch`
- `../experiments/minimax_xpu_kv_offload/patches/xpu-cpu-kv-worker-prototype-20260525.patch`
- `../experiments/minimax_xpu_kv_offload/patches/vllm-xpu-gpu-split-attn-stagea-failed-20260525.patch`

Current design direction:

1. Keep recent/current KV in normal GPU KV blocks.
2. Keep older logical KV blocks in CPU offload storage.
3. Stage old CPU-resident KV chunks into GPU scratch.
4. Run attention over each chunk.
5. Merge partial attention outputs using log-sum-exp/LSE state.
6. Merge old-context attention with normal attention over the live GPU suffix.

This is still a research path, not a serving recipe.

## What GitHub Does Not Include

GitHub has:

- setup scripts
- build scripts
- patch artifacts
- benchmark payloads
- LocalMaxxing responses
- summarized results
- notes and runbooks

GitHub does not include:

- model weights
- Hugging Face tokens or other secrets
- the full raw `/mnt/fast-ai/bench-results` tree
- compiled vLLM/llm-scaler build outputs
- Torch/AOT compile caches

When a note references a raw `/mnt/fast-ai` log or JSON, use the summarized
values in GitHub unless you are on the originating machine.
