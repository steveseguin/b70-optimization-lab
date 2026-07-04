# Qwen3.6 27B INT4 AutoRound vLLM/XPU Lab

This experiment lane tracks bring-up and optimization for:

- Model: `Intel/Qwen3.6-27B-int4-AutoRound`
- Base model: `Qwen/Qwen3.6-27B`
- Quantization: AutoRound INT4, `bits=4`, `group_size=128`, symmetric,
  `packing_format=auto_round:auto_gptq`
- Runtime target: vLLM on Intel XPU / Level Zero
- Hardware target: Intel Arc Pro B70 32 GB, one replica per GPU first

## Immediate Goal

The initial TP1 single-B70 OpenAI-compatible endpoint works, and the lane now
has a strict fresh-response BF16-LM-head baseline plus a faster quality-gated
runtime INT8-LM-head variant. Current optimization work must beat the
`65.27648650325429` tok/s webhie BF16-scale INT8-LM-head row or improve
service/max-context behavior without using warmed/cache/history effects.

Completed first milestone:

1. Downloaded/pinned revision `abc86de19eb1ebbf6a7df4582341325c22ddcb7d`.
2. Served one TP1 replica at `max_model_len=2048`.
3. Passed the OpenAI smoke with thinking disabled.
4. Observed healthy MTP2 acceptance (`105/108` accepted draft tokens after
   manual probes plus smoke).

Current evidence:

- server log:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/servers/tp1-gpu0-port19410-20260703T012317Z.log`;
- smoke JSON:
  `data/qwen36-27b-autoround-openai-smoke-20260703T013020Z.json`.

Current strict best:

- config: Intel checkpoint, TP1, one B70, XPU graph on, `qwen3_next_mtp`,
  `num_speculative_tokens=3`, `max_cudagraph_capture_size=8`,
  `max_num_batched_tokens=1024`;
- env delta: `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1` and
  `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`;
- gate: Qwen realistic suite, chat mode, 12 unique prompts, each prompt once,
  `cached_tokens=0` every row, `return_token_ids=true`;
- conservative result: median `53.522 tok/s` for generated tokens 1-100 after
  TTFT, p10 `48.406`, mean `53.986`;
- evidence:
  `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-promotesource-noacceptedpost-repeat2-realistic128-chat-tokenids-qwensuite-20260703T044519Z.json`;
- compact packet:
  `results/qwen36-27b-autoround-int4-b70/promote-source-noacceptedpost-20260703.json`.

Current fastest quality-gated variant:

- label: `webhie/Qwen3.6-27B-int4-AutoRound + runtime INT8 LM-head
  (BF16 scales)`;
- config: same promote-source MTP3/cg8 recipe plus
  `VLLM_XPU_LM_HEAD_INT8=1` and
  `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16`;
- strict fresh median: `65.276 tok/s`, p10 `59.609`, mean `65.077`,
  `cached_tokens=0`;
- support rows: `65.005` and `64.864 tok/s`;
- same-window/crossover FP32-scale controls: `64.234` and `64.090 tok/s`;
- prior webhie INT8-LM-head record: `64.306 tok/s`;
- full quality gate passed against the Intel INT8-LM-head baseline, including
  1K long-context needle;
- evidence:
  `results/qwen36-27b-autoround-int4-b70/webhie-int8-lmhead-bf16scale-20260703.json`;
- note:
  `notes/2026-07-03-int8-lmhead-bf16-scale-quality-pass.md`.
- LocalMaxxing: approved as `cmr5iu3gk00bfq901nidgcana`.

Prior Intel-checkpoint fastest quality-gated variant:

- label: `AutoRound W4A16 + runtime INT8 LM-head`;
- config: same promote-source MTP3/cg8 recipe plus
  `VLLM_XPU_LM_HEAD_INT8=1`;
- strict fresh median: `62.628 tok/s`, p10 `58.104`, mean `62.998`,
  `cached_tokens=0`;
- repeat: `62.276 tok/s` on GPU3;
- same-window BF16-LM-head control: `53.332 tok/s`;
- full quality gate passed against the BF16-LM-head baseline, including
  1K long-context needle;
- evidence:
  `results/qwen36-27b-autoround-int4-b70/int8-lmhead-20260703.json`;
- patch:
  `patches/qwen36-27b-autoround-int4-b70/vllm-xpu-lm-head-int8-quality-pass-20260703.patch`.

Service-oriented INT8-head variant:

- config: same recipe plus `VLLM_XPU_LM_HEAD_INT8_SCOPE=target`;
- strict fresh median: `61.898 tok/s`, p10 `57.494`, mean `62.432`;
- full quality gate passed against the BF16-LM-head baseline;
- interpretation: target verifier LM-head dominates the speedup; draft-only
  INT8 was essentially BF16 control. Use all-head INT8 for the submitted
  max-throughput row. The older Intel-checkpoint target-only lane passed its
  quality gate, but the later webhie BF16-scale target-only follow-up failed
  repeat32 stability once (`blue, green, red`), so treat target-only as an
  attribution/service idea that must be revalidated per checkpoint/revision and
  scale dtype;
- note:
  `notes/2026-07-03-int8-lmhead-scope-attribution.md`;
- patch:
  `patches/qwen36-27b-autoround-int4-b70/vllm-xpu-lm-head-int8-scope-target-quality-pass-20260703.patch`.

Synthetic search reference:

- config: MTP5/cg16;
- p512/o512 synthetic `vllm-random`: `81.773 tok/s`;
- evidence:
  `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp5-xpugraph1-cg16-specmetrics-p512o512-r3-20260703T031846Z.json`;
- status: diagnostic only. It loses under the realistic chat gate.

Next milestone:

1. Treat Phase 0/1 as complete. The current record family reproduced at
   `65.56930784255283 tok/s`, and the timing refresh is captured in
   `notes/2026-07-04-phase0-phase1-baseline-and-timing.md`.
2. Use four independent TP1 replicas for parallel candidate screening when the
   candidate is cheap enough to run as a config/source screen.
3. Keep synthetic `vllm-random` metrics diagnostic-only.
4. Rerun the Qwen realistic suite with `--return-token-ids` before promoting
   any change.
5. Investigate LM-head/verifier cost with a real mechanism. Recent no-win
   screens closed output-buffer reuse, bonus-token argmax plumbing, draft-only
   row-count shortcuts, Python/chunked INT8 top-1, top-token sampler plumbing,
   and a native compact full-vocab INT8 LM-head top-1 kernel. The compact
   kernel built and was exact, but oneDNN dense GEMM plus argmax was still
   faster at the real Qwen27 shape. The remaining credible lanes are reducing
   the number of LM-head calls/rows per verifier step, improving accepted tokens
   per target verifier step, or finding a oneDNN-integrated top-1/top-k post-op
   that avoids a second reduction launch.
6. Do not keep config-sweeping the current INT8 lane without a new mechanism:
   MTP depth remains k=3, capture size remains cg8, and target-only attribution
   shows the target verifier LM-head is the real bottleneck. The latest
   follow-up closed FP16 scales and webhie target-only BF16 scales as no-promote
   variants; see
   `notes/2026-07-03-scale-scope-followup-no-headline-win.md` and
   `notes/2026-07-03-fused-verifier-top1-design-blocker.md`.
7. Closed source precheck: the default-off spec greedy top-token-ID
   verifier path passed the strict gate at `65.25583870721442 tok/s`, but it
   was flat versus the `65.27648650325429 tok/s` record because
   `get_top_tokens()` still pays the dense LM-head. Treat
   `notes/2026-07-04-spec-greedy-topids-no-headline-win.md` as integration
   groundwork for a future true compact LM-head kernel, not a path to retest by
   itself.
8. Latest closed kernel precheck:
   `notes/2026-07-04-compact-lmhead-top1-kernel-no-win.md`. The native
   `int8_lm_head_top1_w8a8` prototype was exact but slower than dense oneDNN:
   final 8x64 policy measured compact `2.66-2.68 ms` versus dense
   `2.57-2.61 ms` for rows `1-4`, so do not wire it into vLLM.
9. Latest model-variant / MTP-layer audit:
   `notes/2026-07-04-autoround-variant-screening-and-stepidx-audit.md`.
   Local `webhie-Code` and `acyildirimer` AutoRound variants passed the strict
   gate but were slower than the same-window webhie control, and the possible
   `spec_step_idx` MTP fix is a no-op for this lane because the checked
   Qwen27 AutoRound configs all have `mtp_num_hidden_layers=1`.
10. Latest current-recipe depth screen:
    `notes/2026-07-04-webhie-depth-screen-no-win.md`. On the fastest
    webhie/BF16-scale INT8-LM-head recipe, strict same-window MTP4/cg8
    (`60.478 tok/s`), MTP5/cg8 (`59.257 tok/s`), and MTP5/cg16
    (`59.817 tok/s`) all lost to the MTP3/cg8 control (`65.809 tok/s`).
    Treat the control as support/variance only, not a new LocalMaxxing row.
11. Latest shallow-depth coverage screen:
    `notes/2026-07-04-webhie-mtp1-mtp2-depth-coverage-no-win.md`.
    The missing MTP1/MTP2 current-recipe coverage is closed: MTP1/cg8
    `51.246`, MTP2/cg8 `59.589`, MTP3/cg8 control `64.730`, MTP4/cg8
    `59.886`, all `cached_tokens=0` and gate-passing. Keep MTP3/cg8.
12. Latest current-recipe capture-size screen:
    `notes/2026-07-04-webhie-bf16scale-capture-size-screen-no-win.md`.
    On the same webhie/BF16-scale MTP3 recipe, a four-GPU strict same-window
    screen found cg8 remains best: cg4 `64.507`, cg8 control `65.153`, cg16
    `63.500`, cg32 `64.071`, all `cached_tokens=0` and gate-passing. Keep
    `max_cudagraph_capture_size=8` unless a source change alters graph shapes,
    row counts, or acceptance.
13. Latest INT8 GEMM scratchpad ring-size screen:
    `notes/2026-07-04-int8-gemm-scratchpad-ring-screen-no-win.md`.
    The low-level ring-size screen found ring4 highs (`65.708`, `65.817`) but
    paired crossover deltas versus ring1 controls were only `+0.42%` and
    `+0.27%`, below the practical variance band. Do not promote or submit;
    keep default ring behavior unless a future trace shows scratchpad reuse as
    a real issue.
14. Latest variable-depth source precheck:
    `notes/2026-07-04-dynamic-drafter-depth-partial-group-crash.md`.
    A default-off prototype that actually shortened the MTP proposer loop
    crashed with an XPU indexing assert when it created partial speculative
    groups. Do not retry dynamic depth until the Qwen/GDN XPU verifier supports
    partial groups end-to-end.
15. Latest DFlash revisit:
    `notes/2026-07-04-dflash-swa-revisit.md`. Real mixed SWA support crashes
    before readiness because the current DFlash/EAGLE proposer assumes all
    draft layers belong to one KV-cache group. The target-verified
    `all-sliding` single-group diagnostic passed the fresh gate but dropped to
    `20.630 tok/s`, so DFlash remains closed no-win until multi-KV-group draft
    metadata is implemented.
16. Latest DFlash multi-KV implementation attempt:
    `notes/2026-07-04-dflash-multikv-mixed-swa-attempt.md`. The experimental
    patch
    `../../patches/qwen36-27b-autoround-int4-b70/vllm-dflash-multikv-mixed-swa-attempt-20260704.patch`
    gets mixed full/sliding DFlash through startup and graph capture with draft
    KV groups `[64, 65, 66, 67, 68]`, but endpoint testing is still no-win:
    graph mode device-loses during the strict suite, and graph-off/no-async
    shows only about `2-3%` draft acceptance with low-teens or worse generation
    throughput. Preserve the patch as upstream/plumbing research, not as a
    record lane.
17. Latest service-memory flag screen:
    `notes/2026-07-04-language-model-only-no-win.md`.
    `--language-model-only` correctly enters text-only mode and reduced model
    memory from `19.02 GiB` to `18.15 GiB`, but the MTP3/cg8 XPU graph path
    hung before readiness at `Capturing CUDA graphs (decode, PIECEWISE): 0/1`.
    Do not use it for the current strict decode recipe; only revisit for
    non-MTP/non-graph service-memory work or after XPU graph capture changes.
18. Latest scheduler screen:
    `notes/2026-07-04-scheduler-mbt-and-chunked-prefill-screen.md`.
    MBT768 (`64.131 tok/s`) and MBT1280 (`64.346 tok/s`) passed the strict
    fresh gate but lost to the current `65.276 tok/s` record family; disabling
    chunked prefill is invalid for `MAX_MODEL_LEN=2048` / MBT1024. Keep
    `MAX_NUM_BATCHED_TOKENS=1024` and chunked prefill enabled.
19. Latest local EAGLE1 endpoint isolation:
    `notes/2026-07-04-eagle1-endpoint-isolation-matrix.md`.
    The first local EAGLE1 draft looked promising offline (`2.1016` mean
    accepted tokens on held-out calibration starts) but did not survive endpoint
    isolation. Current-state eager k3, default-state graph k3, and
    current-state graph k1 all failed the calibration gate at only
    `19.828-22.410 tok/s`; current-state graph k3 stalled before JSON output.
    The compact summary is
    `../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-eagle1-endpoint-isolation-20260704T094450Z-summary.json`.
    Do not repeat endpoint config sweeps for this draft; future EAGLE work
    starts with diverse chat-style corpus/eval v2 and stronger held-out
    diagnostics.
20. EAGLE corpus/eval v2 tooling:
    `notes/2026-07-04-eagle-corpus-v2-tooling.md`.
    The collector now supports `--suite`, chat mode, request extra JSON, stable
    request IDs, and prompt metadata; the dataset builder copies that metadata
    into `.pt` samples; and offline eval reports acceptance by prompt family.
    This is preparation only, not a speed result, but it is the correct restart
    point if EAGLE is revisited.
21. EAGLE corpus/eval v2 chat smoke:
    `notes/2026-07-04-eagle-corpus-v2-chat-calib-smoke.md`.
    A one-GPU calibration-suite chat collection produced `3840` hidden rows,
    `24` samples, `0` continuity breaks, and metadata on `24/24` samples after
    fixing suffix-tolerant request-ID matching. A tiny two-epoch draft reached
    only `0.240` mean accepted offline, so it is not an endpoint candidate; it
    only proves the metadata path works.
22. EAGLE corpus/eval v2 four-GPU heldout screen:
    `notes/2026-07-04-eagle-corpus-v2-4gpu-heldout.md`.
    The four-GPU runner collected `96` chat prompts, `15360` hidden rows, `96`
    samples, metadata on `96/96` samples, and `0` continuity breaks. A compact
    draft trained on shards `0-2` and evaluated on heldout shard `3` reached
    only `0.489` mean accepted over `1024` starts, far below the prior `2.1016`
    offline draft that still failed endpoint quality. Do not endpoint-test this
    draft; future EAGLE work needs materially stronger data/training/init first.
23. EAGLE corpus/eval v2 followups:
    `notes/2026-07-04-eagle-corpus-v2-followups-closed.md`.
    The staged curriculum improved OOD-family heldout only to `0.616`, a
    balanced task-holdout split scored `0.601`, the old stronger v1 draft
    transferred poorly to v2 heldout (`0.201`), and all-96 training scored only
    `0.438` on the separate calibration suite. Current compact v2 EAGLE is
    closed again; do not endpoint-test these drafts.
24. EAGLE v2 stronger offline screen:
    `notes/2026-07-04-eagle-v2-stronger-offline-screen-no-endpoint.md`.
    The stronger residual/two-layer screen improved heldout only to `0.695`
    mean accepted and separate calibration only to `0.441`. It is
    diagnostic-only and not an endpoint candidate. The reusable runner is
    `scripts/run-eagle-v2-stronger-offline-screen.sh`.

## Folder Map

- `configs/`: reusable env files.
- `scripts/`: downloader, launcher, smoke, and future benchmark helpers.
- `notes/`: chronological run notes.
- `patches/`: patch snapshots for successful and failed source attempts.
- `results/`: compact experiment summaries.
- `quality/`: quality gates and prompt suites as they mature.
- `localmaxxing/`: queued payloads and response copies after valid records.

## Current Research Frontier

The active headline family is now
`webhie/Qwen3.6-27B-int4-AutoRound` with the current promote-source MTP3/cg8
recipe plus default-off runtime INT8 LM-head and BF16 scale storage:
`65.27648650325429 tok/s` median generated-token throughput for tokens 1-100
after TTFT on the strict fresh Qwen realistic suite, with `cached_tokens=0` on
every request and repeat32/1K-needle quality passing. Later same-recipe support
rows reached `65.8-66.4 tok/s`, but a four-GPU reconfirmation landed
`63.97-64.74 tok/s`, so those higher rows are variance/support only and should
not be resubmitted as records.

Older reference points remain useful for attribution: plain MTP3/cg8 was about
`47.6-48.5 tok/s`, and promote-source/no-accepted-postprocess lifted the lane
to `53.5-54.9 tok/s` before the webhie variant and INT8 LM-head work. A fast
invalid flag, `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_FULL_ACCEPT=0`, reached
`51.273 tok/s` on the strict suite and `74.877 tok/s` synthetically, but failed
1024-token needle recall. Tracing explains the lift: the valid path copies
large GDN/Mamba state from the accepted speculative slot back to the running
slot after verification.

Current trace summary:
`data/qwen36-27b-autoround-int4-b70-baselines/mamba-copy-trace-summary-mtp3-cg8-p512o128-20260703T042542Z.json`.

Prompt-processing / long-context service work is tracked separately from the
short-decode record. The current service ladder lives in
`notes/2026-07-04-long-context-ladder-baseline.md`, with suite
`../../repro/qwen36-27b-autoround-int4-b70/long-context-suite-v1.json` and
runner `scripts/run-long-context-ladder.sh`. The latest 32K-capability anchor
uses the same webhie/BF16-scale INT8-LM-head MTP3/cg8 recipe at
`MAX_MODEL_LEN=32768` and passes exact JSON retrieval through `17706` actual
prompt tokens with `cached_tokens=0`, TTFT median `22.443s`, approximate
prefill median `224.67 tok/s`, and after-TTFT short-output median
`60.19 tok/s`. This is a service-lane baseline, not a LocalMaxxing headline
decode row. For production-visible OpenAI content deltas, use the validated
no-parser service variant (`QWEN36_27B_REASONING_PARSER=`), which passed the
same 32K exact-retrieval gate with `reasoning_delta_count=0`.
The MBT follow-up is `notes/2026-07-04-long-context-mbt-screen.md`: same-window
screening kept `MAX_NUM_BATCHED_TOKENS=4096` for the 32K no-parser service lane;
MBT2048 passed but was slower, and MBT8192 stalled without a complete gate
artifact.

The current valid env-only win appears to preserve the accepted-state transition
by reading from the accepted speculative slot as the running source, then
disabling the now-redundant accepted-state postprocess copy. Later timing moved
the current frontier away from that copy path: full LM-head/logits work now
dominates. Bad candidates already closed: blind copy skips, skipping
full-accept state, changing the Triton memcpy block size, exact argmax plumbing
that still computes full logits, draft local-argmax plumbing that still
computes full logits, FP8 LM-head (quality fail), INT8 MTP k2/k4/k5,
INT8 cg4/cg16/cg32, draft-only INT8 LM-head, output-buffer reuse, bonus-token
argmax fast-path, chunked INT8 top-1 argmax-only verification, compressed/full
EAGLE3 (device-loss or too slow), and DFlash (no-win locally).

## Current Entry Points

```bash
cd /home/steve/llm-optimizations

experiments/qwen36-27b-autoround-int4-b70/scripts/download-model.sh

GPU_INDEX=0 PORT=19410 MAX_MODEL_LEN=2048 \
  experiments/qwen36-27b-autoround-int4-b70/scripts/serve-vllm.sh

BASE_URL=http://127.0.0.1:19410/v1 MODEL=qwen36-27b-int4-autoround \
  experiments/qwen36-27b-autoround-int4-b70/scripts/smoke-openai.sh
```

## Local Storage

The pinned Intel snapshot currently lives on the internal NVMe HF cache:

```text
/mnt/fast-ai/llm-cache/hf/hub/models--Intel--Qwen3.6-27B-int4-AutoRound/snapshots/abc86de19eb1ebbf6a7df4582341325c22ddcb7d
```

An external 4 TB USB drive is mounted at `/mnt/usb-models` for overflow model
variants and archived artifacts. Keep active hot-path benchmarks on the
internal NVMe when practical; use `/mnt/usb-models/llm-cache/hf` or
`/mnt/usb-models/models` for additional variants if internal space becomes a
constraint. Do not commit model weights or generated cache contents.

## External References

- Hugging Face:
  https://huggingface.co/Intel/Qwen3.6-27B-int4-AutoRound
- Base model: https://huggingface.co/Qwen/Qwen3.6-27B
- AutoRound: https://github.com/intel/auto-round
- vLLM Qwen3.6 recipe: https://recipes.vllm.ai/Qwen/Qwen3.6-27B
- vLLM Intel quant docs:
  https://docs.vllm.ai/en/stable/features/quantization/inc/
- LocalMaxxing model index: https://www.localmaxxing.com/en/models
- Local vLLM source: `/home/steve/src/vllm`
