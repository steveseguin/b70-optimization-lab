# Qwen3.8 MTP5/M6 Q64xK32 FlashAttention operator preregistration

Date: 2026-08-21

Status: **implemented and hash-frozen for independent review; not launched**.

This is a new campaign, not a retry of the rejected Q8xK64 policy. The previous
candidate stopped at its first candidate eager correctness check and remains a
terminal result under its own preregistration. This screen does not start
vLLM, load the model, authorize a full-25 endpoint run, or change any incumbent
stage.

## Bounded question

The hypothesis is that a Q64xK32 chunk-native device policy can preserve the
production-derived MTP5/M6 operator outputs while reducing captured
FlashAttention time. The new candidate source geometry is
`ShapeQK/ShapePV=<64,32,32>`, `ShapeOut=<64,256>`, subgroup `<8,1,1>`.
No conclusion about this policy is inherited from the Q8xK64 failure.

The runtime call is fixed to:

- FP16 query/KV/output, six rows, 12 local query heads, two local KV heads,
  head dimension 256, paged causal KV, and block size 64;
- KV lengths 128, 1024, 1300, and 2048;
- `is_mix_batch=True` and `VLLM_XPU_FA2_FORCE_CHUNK_DECODE=1`;
- deterministic CPU fixtures, shuffled block tables, and an independent FP32
  CPU oracle;
- logical `xpu:0` inside a one-device process selected with
  `ZE_AFFINITY_MASK=2` or `3`, after a four-B70 `xpu-smi` preflight.

The control is the exact stage
`/home/steve/staged-xpu-commitfix-graphfa-composite-20260820`. Its extension,
interface, device library, and stock library retain the frozen identities from
the prior exact-shape qualifier. Candidate and control must have the same
extension, wrapper, and stock library. Only
`libattn_kernels_xe_2.so` may differ. Every arm proves the exact extension,
device library, and stock library in `/proc/self/maps`; the interface remains
a file/path/hash proof.

Candidate processes set
`VLLM_XPU_FA2_M6_HEAD256_Q64K32_POLICY=1` and require exactly one unadorned
stderr line `VLLM_XPU_FA2_M6_HEAD256_Q64K32_POLICY engaged`. Controls set it
to `0` and require no line containing that environment-variable name. This is
source-backed policy engagement in addition to file and mapping identity.

## Candidate provenance and launch interlock

The candidate source and builder are owned by the separate build lane:

- `patches/vllm-xpu-kernels-qwen38-m6-head256-q64k32-chunk-prefill-20260821.patch`;
- `scripts/build-qwen38-m6-head256-q64k32-attn-override-20260821.sh`;
- build-input artifact `qwen38-m6-head256-q64k32-build-inputs.sha256`;
- graph manifest `qwen38-m6-head256-q64k32-candidate.graph.sha256`;
- stage JSON `qwen38-m6-head256-q64k32-candidate-stage.json`, schema
  `qwen38-mtp5-m6-fa-q64k32-stage-v1`.

The source patch is frozen at SHA-256
`8cbf00eb37faa11e803d39dc43eceabade623cb53907bc48e7a28a40f7738ef1`
and the mode-`0755` build helper at
`eba51acca318e68d176f9de859d90ff3425807cea40e67ced7e38d21fbabe74e`.
The qualifier is frozen at SHA-256
`b390bbc9f29894c355dcb8b4a2e57a5dc0b1a4d3946f816c0e5af2bcef049b1b`.
The mode-`0755` driver is frozen at SHA-256
`34e33671db7800cd31baa6552aef75f483ab0d3295fe2317c436da6618c088ed`;
it embeds the qualifier identity and fails closed if those bytes change.

Suggested immutable roots after that freeze are:

```text
/home/steve/qwen38-m6-head256-q64k32-attn-override-20260821-r1
/home/steve/qwen38-mtp5-m6-fa-q64k32-abba-20260821-r1
```

Neither root may exist before its action, and a stopped result root is never
reused.

## Correctness and failure-preservation contract

For every KV shape the qualifier performs eager and captured XPUGraph replay
checks with caller-owned output poisoning. It requires no residual poison,
bit stability, eager/graph exact digest equality, and CPU-oracle agreement at
`atol=0.02, rtol=0.01`. It separately mutates Q, physical K cache, physical V
cache, and `seqused_k`; each mutation must change output, agree with its newly
derived oracle in eager and graph modes, and restore all inputs before the
next mutation. The validator rederives this inventory and requires exact
control/candidate fixture, oracle, baseline, and mutation digest parity.

The order is fresh-process A-B-B-A on physical GPU 2, then the same on GPU 3.
Candidate B1 is therefore the first post-control gate. Any arm failure stops
the campaign immediately; no B2, A2, second-device, compare, or same-root
retry follows.

Unlike the earlier campaign, a checked failure after staged imports and stderr
capture publishes each of these files atomically before returning nonzero:

- `<success-packet>.stderr.log`, mode `0444`;
- `<success-packet>.failure.json`, mode `0444`, strict schema
  `qwen38-mtp5-m6-fa-q64k32-operator-failure-v1`;
- exact process, stage, mapped-library, marker, harness, completed-case-prefix,
  and success-path absence evidence;
- parsed CPU-oracle mismatch counts, indexes, tolerances, mode, replay, and KV
  when PyTorch emits the expected assertion format.

The driver validates that receipt before returning the arm's nonzero status.
If failure occurs before the receipt boundary, the driver says so and still
stops. A candidate-specific correctness classification is allowed only when
the marker and all three mapped-library gates passed and the error metadata
rederives from the preserved message. Thus a source presence or partial load
cannot be mislabeled as a policy correctness result.

## Timing and decision gates

Only an eight-packet correctness-valid campaign reaches comparison. Each arm
records 40 independent graph-replay samples with 100 calls per sample after
warmup. Paired A-B-B-A bootstrap confidence intervals are computed separately
per physical GPU.

Every gate below is conjunctive on both GPUs:

- exact control/candidate correctness and mutation parity;
- at KV 1024, 1300, and 2048, the 95% lower bound for paired
  control-minus-candidate saving is greater than zero;
- at KV 128, the 95% upper bound for candidate-minus-control regression is at
  most `+2.0 us/call`;
- at KV 1300, central saving is at least `21.844 us/call`, equivalently
  `0.3495 ms` per 16 FlashAttention calls.

The historical single-arm `151.46586 us/call` observation is context, not an
absolute candidate gate: applying it to both devices would combine a prior
GPU2 A1 with new paired evidence and falsely strengthen the preregistration.
Eager timing is context only; the primary gate is captured graph replay.

Passing qualifies this exact operator candidate only for a separately
preregistered endpoint campaign. It is not endpoint performance, target
exactness, or promotion. Any correctness, identity, mapping, marker, stability,
parity, confidence-interval, short-KV, or central-saving failure rejects this
policy with no same-policy retry.

## Commands after final freeze only

```bash
builder=/home/steve/llm-optimizations/experiments/qwen38-27b-b70/scripts/build-qwen38-m6-head256-q64k32-attn-override-20260821.sh
driver=/home/steve/llm-optimizations/experiments/qwen38-27b-b70/scripts/run-20260821-qwen38-mtp5-m6-fa-q64k32-operator-abba.sh
build_root=/home/steve/qwen38-m6-head256-q64k32-attn-override-20260821-r1
result=/home/steve/qwen38-mtp5-m6-fa-q64k32-abba-20260821-r1
manifest="$build_root/qwen38-m6-head256-q64k32-candidate-stage.json"

WORK_ROOT="$build_root" "$builder" --build
"$driver" check "$manifest"
"$driver" run "$manifest" "$result"
"$driver" compare "$result"
```

Do not run those commands while any hash placeholder remains.
