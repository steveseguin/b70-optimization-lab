# Qwen27 Branch/Regenerate Trace Probe And XPU Module Restore

Date: 2026-07-06

Classification: diagnostic instrumentation and runtime repair; no endpoint
mutation, no headline result, no LocalMaxxing submission.

## Purpose

The current valid Qwen27 INT4 lane is still `68.23626314761921 tok/s` with
target INT8 LM-head BF16 scales, draft INT4 LM-head BF16 scales, ReplaySSM
exact GDN state handling, MTP3/cg8, and strict fresh/cached-zero validation.

The next credible speed lane is not another config sweep.  The branch/regenerate
cost model says MTP3 can only target a narrow `~100 tok/s` ceiling, but the
state transaction pieces are useful infrastructure for deeper speculation.  We
therefore added a default-off trace probe to measure legal branch opportunities
on real endpoint runs before mutating any state.

## Trace Patch

Source patch artifact:

`patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-branch-regen-trace-probe-20260706.patch`

The active source patch adds `VLLM_XPU_BRANCH_REGEN_TRACE=1`, which writes
`branch_regen_candidates` records into the existing
`VLLM_XPU_COW_WORKER_TRACE_FILE` stream.

Important: this is trace-only.  It reads/copies `valid_sampled_tokens_count`,
`next_token_ids`, `sampled_token_ids`, and `scheduled_spec_decode_tokens`, then
logs derived counts.  It does not change scheduler state, sampler output, GDN
state, input tokens, draft tokens, or accepted counts.

For normal non-draft-only MTP rows, the accepted draft prefix candidate is:

```text
min(max(raw_visible_count - 1, 0), scheduled_spec_len)
```

The `-1` excludes the target-owned replacement/bonus token.  Draft-only rows do
not subtract one.  Suppressed bonus/replacement modes can make this count
diagnostic rather than authoritative, so any future mutating patch must recheck
the exact scheduler masks and row identity.

Summarizer:

`scripts/summarize-qwen27-branch-regen-trace.py`

## Runtime Repair Before Probe

The first trace endpoint attempt failed before server startup:

`/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-branchregen-trace-20260706T184844Z`

Although the launcher exported `VLLM_TARGET_DEVICE=xpu`, vLLM resolved
`UnspecifiedPlatform`.  Root cause was not torch/XPU availability (`torch.xpu`
reported 4 devices); it was the local `vllm_xpu_kernels` package:

- `_C.abi3.so` linked against `libsycl.so.9`;
- `_moe_C.abi3.so` linked against `libsycl.so.9`;
- `_xpu_C.abi3.so` was already the good `libsycl.so.8` build.

The bad `_C/_moe_C` modules came from the earlier oneAPI 2026 umbrella
environment problem.  vLLM's XPU platform plugin imports `_C`, `_moe_C`, and
`_xpu_C`; the broad platform-probe exception hid the import error and caused
device inference to fail.

Repair performed:

```bash
cd /home/steve/src/vllm-xpu-kernels
stamp=$(date -u +%Y%m%dT%H%M%SZ)
cp -a vllm_xpu_kernels/_C.abi3.so \
  "vllm_xpu_kernels/_C.abi3.so.pre-restore-sycl8-${stamp}"
cp -a vllm_xpu_kernels/_moe_C.abi3.so \
  "vllm_xpu_kernels/_moe_C.abi3.so.pre-restore-sycl8-${stamp}"
cp -a build/temp/_C.abi3.so vllm_xpu_kernels/_C.abi3.so
cp -a build/temp/_moe_C.abi3.so vllm_xpu_kernels/_moe_C.abi3.so
```

Verification after repair:

- `torch.xpu.is_available() == True`;
- `torch.xpu.device_count() == 4`;
- imports pass for `vllm_xpu_kernels._C`, `_moe_C`, `_xpu_C`, and
  `vllm.platforms.xpu`;
- `DeviceConfig().device_type == "xpu"`.

The second trace attempt then reached engine init but failed in FA2 attention:

`/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-branchregen-trace-20260706T185159Z`

The runtime error was:

```text
AttributeError: '_OpNamespace' '_vllm_fa2_C' object has no attribute 'varlen_fwd'
```

Root cause was the same oneAPI generation mismatch, but in the FA2 pair:

- active `_vllm_fa2_C.abi3.so` linked against `libsycl.so.9`;
- active `libattn_kernels_xe_2.so` linked against `libsycl.so.9`;
- the import failure is caught by `flash_attn_interface.py`, so the missing op
  only appears later when graph capture or eager attention calls `varlen_fwd`.

Attempting to rebuild `_vllm_fa2_C` with oneAPI 2025.3 pulled the 1.6 GB
`attn_kernels_xe_2` target and stalled on a long compile, so the safer repair
was to restore the known sycl8 pair from the digest tree while preserving the
broken sycl9 pair:

```bash
cd /home/steve/src/vllm-xpu-kernels
stamp=$(date -u +%Y%m%dT%H%M%SZ)
cp -a vllm_xpu_kernels/_vllm_fa2_C.abi3.so \
  "vllm_xpu_kernels/_vllm_fa2_C.abi3.so.pre-restore-sycl8-${stamp}"
cp -a vllm_xpu_kernels/libattn_kernels_xe_2.so \
  "vllm_xpu_kernels/libattn_kernels_xe_2.so.pre-restore-sycl8-${stamp}"
cp -a /home/steve/src/vllm-xpu-kernels-digest-sycl8-20260612dj/vllm_xpu_kernels/_vllm_fa2_C.abi3.so \
  vllm_xpu_kernels/_vllm_fa2_C.abi3.so
cp -a /home/steve/src/vllm-xpu-kernels-digest-sycl8-20260612dj/vllm_xpu_kernels/libattn_kernels_xe_2.so \
  vllm_xpu_kernels/libattn_kernels_xe_2.so
```

Verification after the FA2 restore:

- imports pass for `_C`, `_moe_C`, `_vllm_fa2_C`, `_xpu_C`, and
  `vllm.platforms.xpu`;
- `hasattr(torch.ops._vllm_fa2_C, "varlen_fwd") == True`;
- `DeviceConfig().device_type == "xpu"`.

Keep using oneAPI 2025.3 for rebuilds.  Do not use umbrella
`/opt/intel/oneapi/setvars.sh` when it selects 2026, because it creates modules
that require `libsycl.so.9` and break the vLLM XPU platform probe.

## Probe Command

The rerun uses the current best recipe plus tracing:

```bash
cd /home/steve/llm-optimizations
MODEL_DIR=/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e \
GPU_INDEX=0 PORT=19420 RUN_QUALITY=0 QUALITY_SKIP_LONG_CONTEXT=1 \
VLLM_XPU_BRANCH_REGEN_TRACE=1 \
VLLM_XPU_COW_WORKER_TRACE_FILE="$RUN_DIR/branch-regen-cow-trace.jsonl" \
VLLM_XPU_COW_WORKER_TRACE_MAX_LINES=2000 \
VLLM_XPU_COW_WORKER_TRACE_RANK=0 \
VLLM_XPU_GDN_REPLAYSSM_SPEC=1 \
VLLM_XPU_GDN_REPLAYSSM_SPEC_CACHE_LEN=8 \
VLLM_XPU_GDN_REPLAYSSM_TORCH_FALLBACK=0 \
VLLM_XPU_GDN_REPLAYSSM_STAGE_CONV_TORCH_FALLBACK=0 \
VLLM_XPU_GDN_REPLAYSSM_COMMIT_IN_FORWARD=1 \
VLLM_XPU_GDN_REPLAYSSM_SLOT_MGMT_TORCH_FALLBACK=1 \
VLLM_XPU_DRAFT_LM_HEAD_INT4=1 \
VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE=128 \
VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE=bf16 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}' \
experiments/qwen36-27b-autoround-int4-b70/scripts/run-vllm-candidate.sh
```

When the endpoint run completes, summarize with:

```bash
scripts/summarize-qwen27-branch-regen-trace.py \
  --trace "$RUN_DIR/branch-regen-cow-trace.jsonl" \
  --out-json data/qwen36-27b-autoround-int4-b70-baselines/<label>-branch-regen-trace-summary.json \
  --out-md data/qwen36-27b-autoround-int4-b70-baselines/<label>-branch-regen-trace-summary.md
```

## Next Decision

If the trace confirms the same narrow branchable surface as the existing
top-k64 cost model, branch/regenerate remains useful infrastructure but not the
main `125+ tok/s` path.  A serious `100+` attempt then needs either lower
verifier-step cost, deeper legal speculation, or a stronger drafter; this trace
only prevents us from mutating state with the wrong accepted-prefix boundary.

## Completed Probe Result

Successful trace run:

`/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-branchregen-trace-20260706T190432Z`

Promoted summaries:

- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-branchregen-trace-20260706T190432Z-candidate-summary-20260706T190432Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-branchregen-trace-20260706T190432Z-branch-regen-trace-summary.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-branchregen-trace-20260706T190432Z-branch-regen-trace-summary.md`

Benchmark status:

- strict fresh-response gate passed: fixed realistic suite, each prompt once,
  `cached_tokens=0` for every request;
- diagnostic throughput: median `65.07841008395174 tok/s`, mean
  `65.79233661731273 tok/s`, p10 `59.26438834691144 tok/s`;
- diagnostic only, not a headline record, because the trace hook copies
  sampler/scheduler tensors to CPU and can perturb timing;
- quality suite was intentionally skipped for this probe.

Trace result over the first `2000` COW-worker events / `220` scheduled
verifier rows:

| metric | value |
| --- | ---: |
| scheduled rows | 220 |
| partial rejects | 134 (`60.91%`) |
| full accepts | 86 (`39.09%`) |
| mean raw visible tokens | 2.6727 |
| mean accepted draft prefix | 1.6727 |
| mean scheduled spec len | 3.0000 |
| remaining branchable draft rows after partial rejects | 292 |

Histograms:

```json
{
  "hist_draft_prefix_count": {"0": 56, "1": 46, "2": 32, "3": 86},
  "hist_first_reject_index": {"0": 56, "1": 46, "2": 32},
  "hist_raw_visible_count": {"1": 56, "2": 46, "3": 32, "4": 86},
  "hist_scheduled_spec_len": {"3": 220}
}
```

Conclusion: the trace confirms MTP3 is averaging only `1.67` accepted draft
tokens per verifier row (`2.67` raw visible including the target-owned
replacement/bonus token). Branch/regenerate remains useful infrastructure for
partial-reject recovery, but the measured branchable surface is too narrow to
be the primary `125+ tok/s` path by itself. The next serious lane should reduce
per-step verifier / LM-head cost or use a stronger legal drafter; otherwise the
current MTP3 acceptance distribution keeps the ceiling too low.
