# Qwen3.8 native SYCL GDN prefill/state stability preregistration

Date: 2026-08-20

Status: **implemented; GPU qualification and screen not started**

## Question and scope

The sealed pad-on TP2/MTP5 A2, B2, and C1 runs retained unstable prompt 6, 11,
and 24 families. Does ordinary native SYCL GDN prefill fail bitwise output or
state stability under complete-cache reset and finite stale-output poison at
those requests' exact production prompt lengths?

This raw-op control is distinct from the closed invalid M1 replay microscope.
It does not start vLLM, load model weights, replay request IDs, use a compile
cache, or measure throughput. A clean result bounds this synthetic direct-op
surface only; it cannot close graph, scheduler, allocation-history, or compiled
handoff hypotheses.

Harness:
[`../scripts/check-qwen38-native-gdn-prefill-state-stability.py`](../scripts/check-qwen38-native-gdn-prefill-state-stability.py)

## Frozen identity and production shapes

The harness fails closed on the pinned vLLM Python environment, A2 identity,
model config/manifest, tracked-clean kernel source at `2dd55f380...`, complete
20-entry composite manifest `47861e839...`, imported `_xpu_C` hash
`4dd336013...`, and the post-import `/proc/self/maps` path and SHA of staged
`libgdn_attn_kernels_xe_2.so` (`c194e28dd...`). It also requires one visible
logical XPU and an exact physical-GPU `ZE_AFFINITY_MASK` of `2` or `3`.
The staged package directory must be the first nonempty `LD_LIBRARY_PATH`
component, and the mapped GDN path/hash must be unchanged at postflight.

The model config proves `text_config.mamba_ssm_dtype=float32`. The direct call
therefore uses:

- TP2 local heads `8/24`, head dimensions `128/128`;
- FP16 QKVZ/BA, outputs, convolution weights/state, and `dt_bias`;
- FP32 SSM state and `A_log`;
- QKVZ/BA/convolution widths `8192/48/5120`;
- production per-slot conv layout `[slots,8,5120]`; this harness uses eight
  slots, with active history columns `0:3` and MTP5 reserved tail `3:8`;
- `has_initial_state=false`, one prefill, zero decodes, reordered input;
- exact server prompt-token counts 83, 61, and 849 for prompts 6, 11, and 24.

CPU-generated source tensors make paired GPU2/GPU3 inputs byte-identical.
Every fresh process uses the same CPU fixture for a given token length; the
seed does not include process index or device. Before every call, QKVZ, BA,
and the complete conv/SSM cache are restored to that fixture. Rows rotate
through non-null slots `1,1,2,4,7`; those rows intentionally contain distinct
fixture values. Core output and Z alternate finite poison values
`+31744/-31744`; opposite-poison calls must yield equal finite results. The
sentinel counts are recorded but are not individually a failure because a
legitimate output may equal a sentinel. Active conv `0:3`, SSM, core, and Z
must remain bit-identical. Reserved conv `3:8`, nonselected state rows,
QKVZ/BA working tensors, every immutable source tensor, and metadata must
remain unchanged. QKVZ, BA, and every full nonselected conv/SSM row are
snapshotted and checked after every call, including every queued call before
the next batch begins.

Two execution modes share the same inputs and reset semantics:

- `isolated`: synchronize immediately before and after every native call;
- `queued`: enqueue restore/call/snapshot sequences in bounded batches of 16,
  then synchronize once per batch. This preserves completion-order sensitivity
  without retaining an unbounded snapshot set.

The JSON records exact identity, loaded/mapped paths and hashes, operator
schema, execution order, seeds, inputs, every output/state digest and bitwise
comparison, reserved-tail checks, immutable-source checks, call count, and
stage and mapped-library postflight. The CPU `compare` subcommand validates the
exact preregistered result set, execution order, call count, seed, paired-device
digests, and reference digests across every fresh process and both modes. It
rederives the current script SHA and shape contract and inspects every recorded
observation rather than trusting the per-run summary.

An observed tensor/state mismatch is a valid scientific positive: isolated
mode stops after that call, queued mode stops after the containing batch, no
later case runs, and a `status=fail, valid=true` JSON records the actual call
count and first-failure coordinates. Identity, device, mapping, or runtime
exceptions instead produce `status=invalid, valid=false` JSON and exit 2.

## Staged contract

The 20-call qualification is an integration gate only and cannot support a
hypothesis-closing claim. Run it once per GPU as fresh process index `9000`, in
GPU2 then GPU3 order, then compare. Stop on any failure.

If qualification passes, run exactly four fresh processes per GPU at 256 calls
per token length per mode. Every main `run` validates and records the exact
qualification comparison before preflight or torch import; it cannot launch
without that pass artifact. The final gate consumes all eight main JSONs at once:

| Process | Prompt order | Mode order |
| ---: | --- | --- |
| 0 | `6,11,24` | `isolated,queued` |
| 1 | `24,11,6` | `queued,isolated` |
| 2 | `11,24,6` | `isolated,queued` |
| 3 | `6,24,11` | `queued,isolated` |

The main screen contains `1024` calls per token length, physical GPU, and mode:
`4 processes * 256 calls`. Across three lengths, two GPUs, and two modes it
contains 12,288 native calls. Under an explicitly conditional independent-call
model, that gives about 95.4% probability of seeing at least one event whose
rate is 1/4,000; zero events give a 95% Poisson upper bound near `2.44e-4`
across the pooled screen. Scheduling events need not be independent, and the
pooled bound does not transfer to any one length/mode/device subgroup or to the
server. Therefore even a completely clean screen is a bounded negative, not
proof of determinism and not authorization to resume speed sweeps.

## Command template

No GPU command is authorized until the measuring host is idle and healthy.
Every `run` invocation below is a fresh Python process, is sequential, and
refuses to overwrite an existing result.

```bash
set -euo pipefail
cd /home/steve/llm-optimizations

common_ld=/home/steve/staged-xpu-commitfix-graphfa-composite-20260820/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib
script=experiments/qwen38-27b-b70/scripts/check-qwen38-native-gdn-prefill-state-stability.py
data=experiments/qwen38-27b-b70/data

run_one() {
  gpu=$1
  process_index=$2
  calls=$3
  prompt_order=$4
  mode_order=$5
  qualification_json=${6:-}
  qualification_args=()
  if [ -n "$qualification_json" ]; then
    qualification_args=(--qualification-json "$qualification_json")
  fi
  ZE_AFFINITY_MASK="$gpu" PYTHONDONTWRITEBYTECODE=1 \
    LD_LIBRARY_PATH="$common_ld" \
    /home/steve/.venvs/vllm-xpu/bin/python "$script" run \
    --physical-gpu "$gpu" --process-index "$process_index" \
    --calls "$calls" --order "$prompt_order" --mode-order "$mode_order" \
    "${qualification_args[@]}" \
    --json-out "$data/2026-08-20-native-gdn-prefill-p${process_index}-gpu${gpu}.json"
}

# Qualification: two fresh processes and one exact two-file gate.
run_one 2 9000 20 6,11,24 isolated,queued
run_one 3 9000 20 6,11,24 isolated,queued
/home/steve/.venvs/vllm-xpu/bin/python "$script" compare \
  --contract qualification \
  --gpu2-json "$data/2026-08-20-native-gdn-prefill-p9000-gpu2.json" \
  --gpu3-json "$data/2026-08-20-native-gdn-prefill-p9000-gpu3.json" \
  --json-out "$data/2026-08-20-native-gdn-prefill-qualification-compare.json"

# Only after qualification passes: eight fresh main processes, sequentially.
qualification_json="$data/2026-08-20-native-gdn-prefill-qualification-compare.json"
run_one 2 0 256 6,11,24 isolated,queued "$qualification_json"
run_one 3 0 256 6,11,24 isolated,queued "$qualification_json"
run_one 2 1 256 24,11,6 queued,isolated "$qualification_json"
run_one 3 1 256 24,11,6 queued,isolated "$qualification_json"
run_one 2 2 256 11,24,6 isolated,queued "$qualification_json"
run_one 3 2 256 11,24,6 isolated,queued "$qualification_json"
run_one 2 3 256 6,24,11 queued,isolated "$qualification_json"
run_one 3 3 256 6,24,11 queued,isolated "$qualification_json"

# The main gate requires exactly process indices 0..3 on each GPU and validates
# all eight files together, including cross-process reference digests. It is
# mechanically bound to the exact successful qualification comparison.
/home/steve/.venvs/vllm-xpu/bin/python "$script" compare \
  --contract main \
  --qualification-json \
    "$data/2026-08-20-native-gdn-prefill-qualification-compare.json" \
  --gpu2-json \
    "$data/2026-08-20-native-gdn-prefill-p0-gpu2.json" \
    "$data/2026-08-20-native-gdn-prefill-p1-gpu2.json" \
    "$data/2026-08-20-native-gdn-prefill-p2-gpu2.json" \
    "$data/2026-08-20-native-gdn-prefill-p3-gpu2.json" \
  --gpu3-json \
    "$data/2026-08-20-native-gdn-prefill-p0-gpu3.json" \
    "$data/2026-08-20-native-gdn-prefill-p1-gpu3.json" \
    "$data/2026-08-20-native-gdn-prefill-p2-gpu3.json" \
    "$data/2026-08-20-native-gdn-prefill-p3-gpu3.json" \
  --json-out "$data/2026-08-20-native-gdn-prefill-main-compare.json"
```

## Stop and interpretation rules

1. Stop on any identity, import/mapping, device, shape, engagement, non-finite,
   poison-invariance, reserved-tail, immutability, state-scope, or stage/mapping
   postflight gate.
   Preserve produced JSON; do not rerun or overwrite that process index.
   The main comparison is forbidden unless the exact current-script/current-
   shape qualification comparison is supplied and passes schema validation.
2. A within-device core/Z/active-conv/SSM mismatch supports native prefill
   instability. A queued-only failure localizes completion/order sensitivity;
   a failure in isolated mode survives explicit call boundaries.
3. If each device passes internally but paired comparison fails on identical
   input digests, classify the operator as device-dependent.
4. Qualification success authorizes only the main screen. Main-screen success
   is the bounded negative defined above, never a hypothesis closure.
