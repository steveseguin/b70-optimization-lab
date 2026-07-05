# Qwen27 GDN Packed Decode With Source: No Win

Date: 2026-07-05

## Question

Can the current record family recover some target-forward/state overhead by
using the packed one-token GDN decode path even when
`running_state_source_indices_tensor` is present?

The timing/frontier audit showed the recurrent MTP wrapper is cheap and the
real cost is target forward plus GDN/spec-state handling. The current packed
non-spec decode helper already contains a source-promotion call, but the outer
gate excluded it whenever accepted-source indices existed. This experiment
tested a narrow default-off source patch rather than a broad state shortcut.

## Patch

Patch artifact:

```text
patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-gdn-packed-decode-with-source-no-win-20260705.patch
```

The patch added `VLLM_XPU_GDN_PACKED_DECODE_WITH_SOURCE=1`, allowed
`_forward_core_decode_non_spec()` when source indices are present, and promoted
both conv and SSM source rows before the packed one-token decode. Default
behavior stayed unchanged.

The active vLLM source was reverted after the result because this was not a
speed win.

## Same-window strict fresh screen

Harness: `experiments/qwen36-27b-autoround-int4-b70/scripts/run-vllm-candidate.sh`

Both rows used the current webhie/BF16-scale INT8-LM-head MTP3/cg8 record
recipe, one B70 each, fixed realistic Qwen suite, chat mode, 12 unique prompts
run once, `return_token_ids=true`, and `cached_tokens=0` on every request.
`RUN_QUALITY=0` because the first strict screen was enough to reject the speed
change.

Candidate:

```text
label=qwen27-gdn-packed-source-20260705Tpackedsource01
GPU_INDEX=0 PORT=19420
VLLM_XPU_GDN_PACKED_DECODE_WITH_SOURCE=1
summary=data/qwen36-27b-autoround-int4-b70-baselines/qwen27-gdn-packed-source-20260705Tpackedsource01-candidate-summary-20260705Tpackedsource01.json
run_dir=/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-gdn-packed-source-20260705Tpackedsource01-20260705Tpackedsource01
```

Result:

- strict fresh gate: passed;
- cached tokens: all zero;
- smoke: passed;
- median tok/s tokens 1-100 after TTFT: `65.07664099605498`;
- p10: `54.11211728803905`;
- mean: `63.294352237082165`;
- TTFT median: `622.809877502732 ms`.

Same-window control:

```text
label=qwen27-gdn-packed-source-control-20260705Tpackedsource01
GPU_INDEX=1 PORT=19421
summary=data/qwen36-27b-autoround-int4-b70-baselines/qwen27-gdn-packed-source-control-20260705Tpackedsource01-candidate-summary-20260705Tpackedsource01.json
run_dir=/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-gdn-packed-source-control-20260705Tpackedsource01-20260705Tpackedsource01
```

Result:

- strict fresh gate: passed;
- cached tokens: all zero;
- smoke: passed;
- median tok/s tokens 1-100 after TTFT: `65.63144011086737`;
- p10: `57.86312521612205`;
- mean: `64.15167558594969`;
- TTFT median: `626.0912176221609 ms`.

## Decision

Closed no-win. The candidate lost to the same-window control
(`65.08` vs `65.63` tok/s), so there is no reason to run repeat quality or
promote the patch.

This also suggests that simply copying accepted source rows into the packed
one-token helper does not remove meaningful overhead in the current record
family. Future GDN work should target an exact accepted-prefix transaction or
native graph-safe tape/commit path, not another Python-level promotion shortcut.
