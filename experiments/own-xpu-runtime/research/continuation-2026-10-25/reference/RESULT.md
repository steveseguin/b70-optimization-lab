# Independent-reference discrepancy investigation, 2026-10-25

The six output disagreements remain unexplained at the end-to-end level. This
audit confirms their positions and establishes specific arithmetic differences
that the earlier matmul control did **not** test. It does not change native
arithmetic or qualify the engine as independently exact.

## What the retained result actually establishes

[The offline result](summary.json) independently validates every scored row
against its retained input token sequence: 5,959 of 5,965 predictions agree
(99.899413%). Twelve final rows predict beyond the supplied sequence and are
correctly excluded. This is teacher-forced agreement: the CPU consumes the
engine's tokens. It is not equality of independently generated answers.

| Prompt | Absolute prediction position | Output index, zero based | CPU argmax | Engine token | CPU top-1 minus engine-token logit |
|---|---:|---:|---:|---:|---:|
| technical-guide | 243 | 175 | 16568 | 6343 | 0.1001244 |
| technical-guide | 329 | 261 | 15 | 8152 | 0.0148182 |
| technical-guide | 488 | 420 | 13662 | 19023 | 0.0191899 |
| technical-guide | 530 | 462 | 5427 | 10202 | 0.0044346 |
| technical-guide | 540 | 472 | 82459 | 16196 | 0.0093823 |
| bug-report-synthesis | 526 | 456 | 35239 | 92217 | 0.0003223 |

The engine token is the CPU runner-up in each case. The loose historical
description “near-ties” is not a causal explanation: the largest margin is
0.1001244, and no retained per-layer comparison shows why it changes sign.
The four later technical-guide discrepancies occur after teacher forcing has
already selected a different prefix from the CPU's own greedy choice at index
175. Do not describe those as four additional free-running disagreements.

All six survive the retained F32-lane matmul and both RoPE controls without an
argmax change. The maximum observed emitted-token logit difference is 4e-5 for
the matmul control. These files contain top 20 and emitted-token logits, not all
vocabulary logits; their observed maximum cannot certify a full-logit bound.
The old statement ruling out “matmul summation order” does not rule out
different reductions in normalization, GDN recurrence, or attention.

The original scripts depend on inherited `GGML_CPU_EXACT_F64=1` and, for the
lane control, `GGML_CPU_EXACT_ACC=f32lane`. Those values are not explicitly set
in their retained `run_all.sh` / external `run.sh`, and the tool does not print
them. The surviving rows do differ as reported; missing environment receipts
are a replay provenance limitation, not evidence that the historical run used
the wrong mode. A new qualification must record the effective environment.

## Operator-level evidence

[operator_probe.cpp](operator_probe.cpp) links the actual retained CPU reference
`libggml-cpu.a` and includes the actual native `specialised.hpp`. Compilation
uses `-ffp-contract=off`; CPU library SIMD intrinsics still explicitly use FMA.
The source/library hashes and exact compiler command are in the result.
It loads no weights and creates no GPU context.

1. **RMS normalization uses different sums.** CPU `ops.cpp` accumulates F32
   squares into `ggml_float` (double), divides in double, then converts the mean
   to F32. Native `specialised::subtree/upper` uses the prescribed F32 tree.
   A fixed 2,560-element witness changes the inverse by one ULP and all 2,560
   normalized outputs. However, the actual retained PP2 position 118 embedding
   has a one-ULP mean difference and **zero normalized-output differences**.
   Therefore this source difference alone is not evidence of the first actual
   divergence, much less the cause of any of the six token disagreements.
2. **GDN query normalization changes algebra as well as reduction.** CPU
   `models/models.h:build_gdn_l2_norm` computes RMSNorm with epsilon/128, then
   scales by 1/sqrt(128). Native divides raw Q by sqrt(sum(Q²)+epsilon).
   For the actual frozen position 118 layer 0, head 0 Q, these source equations
   differ in 38/128 values, maximum 2.9802322387695312e-8. Holding the sum
   identical still changes exactly those 38 values: this isolates the
   normalization formula. It does not establish the exact device intermediate,
   as the output replay qualification below demonstrates.
3. **GDN state update and dot products use FMA on the reference CPU.** The
   fused GDN calls `ggml_vec_mad_f32` and `ggml_vec_dot_f32`, outside the patched
   MUL_MAT/MUL_MAT_ID dispatch. For state=-1, delta=1-2^-23, key=1+2^-23, the
   native separate update gives zero; the actual CPU SIMD update preserves the
   exact residual -2^-46. A fixed 128-element dot gives the same difference.
   This is a concrete operation-level counterexample to assuming the F32-lane
   matmul control equalizes all recurrence arithmetic.
4. **GDN output scaling is placed differently.** CPU multiplies the completed
   output dot by 1/sqrt(128); native scales Q before the dot. Even using the
   same native reduction for both alternatives, a fixed rational input changes
   the result by two ULPs. This is a separate uncovered arithmetic boundary.

These are established local numerical differences, not claims that changing
one of them will repair the six outputs. No whole-model RMS, FMA, or recurrence
change is justified by these witnesses alone.

## Existing-state output replay did not qualify

The PP2 dump contains actual `blk.0.gdn.conv`, post-update
`blk.0.gdn.state`, and `blk.0.gdn.y`. The audit verifies their index hashes and
reads approximately 3.2 MiB. It never reconstructs an earlier state by dividing
out a decay or reversing an update.

Replaying the native source equation on the CPU, with post-update state and Q
reconstructed from the saved convolution output, differs from the saved GPU y
in **3,596/6,144** values (maximum 2.9802322387695312e-8). Thus the raw saved Q
is insufficient to establish exact consumed Q at this boundary on the CPU.
Explicit reciprocal/scale-placement alternatives were recorded as diagnostics;
none matches all values. The closest differs in 400 values, and is **not**
accepted as the kernel's semantics. Compiler lowering, math instructions, and
the intermediate mapping remain to be checked with the actual consumed Q.

Using the reference normalization, CPU dot, and output scale on the same saved
post-update state differs in 4,539 values. That number cannot yet be attributed
to just the CPU dot: the native reconstruction control failed. No end-to-end
claim follows from these real-operand comparisons.

## Focused next qualification

Root owns GPU activity and the memory budget. No new model run was started.
The current LAN process's roughly 29 GiB lookup table plus model mappings must
be included before admitting a full CPU oracle alongside it.

Use the original technical-guide retained input, model bytes, F32 policy, and
zero cache reuse. Absolute position 243 consumes `tokens[243]` and predicts
`tokens[244]` (engine 6343, reference 16568). A native target-only request with
the first 244 tokens as the prompt and one generated token reaches that boundary
without depending on recursive drafting. Preserve full original 581 CPU input
tokens and 256-token batching for the first repeat: changing batch shape before
reproducing the historical result creates another confound. Record effective
`GGML_CPU_EXACT_F64=1`, F32 KV, all diagnostic flags, and binary/source hashes.

The first narrow device capture should make the **local replay** exact before
attempting a causal model change:

- At layer 0 position 0 or 243, capture the exact normalized/scaled Q consumed by
  GDN: 16 key heads × 128 F32 values (8 KiB), plus the corresponding raw conv Q,
  post-update F32 state, output y, and absolute position/input token. These must
  come from the same invocation and kernel implementation. Gate/beta are not
  needed to replay the final dot from post-update state.
- Replay native dot on that consumed Q and saved state. Require all 6,144 y
  values bit-identical before replacing only the dot with CPU
  `ggml_vec_dot_f32`. Then separately compare normalization and output scaling.
- To examine the **state update**, additionally capture the actual pre-update
  state, normalized K, decay, and beta; do not infer them by reversing F32
  arithmetic. Check native replay first, then substitute one operator only.
- For the earliest model-level divergence, compare embedding and layer 0 HC
  norm/low/act/gate/mix before GDN, followed by per-layer streams and MoE top 10
  IDs. Matching only post-layer streams cannot identify the first arithmetic
  operation. A top 10 ID change is a candidate amplification point, not proof
  of a normalization bug.

Existing `--retain-steps` retains post-layer streams, not selected internal
operands. `state_dump` gives last-writer buffers but cannot expose the scaled Q
inside GDN. The engine audit recommends an opt-in capture with absolute
position, explicit buffer allowlist, writer label/occurrence, type/shape/hash,
and ordered readback. Any capture run is diagnostic timing only. The first
capture should not modify production arithmetic or shared runtime state.

[capture-request.json](capture-request.json) supplies the exact 244-token native
prefix, expected output, original input hash, and dispatch hash. The active
dispatch maps `gdn.recurrence` to `round2`; `adapter.cpp` selects implementation 2
and `round2_submit.cpp:gdn_device`. This path holds Q in per-lane `q[4]`
registers; its scratch allocation is only one float. No existing prepared
scratch contains normalized Q. A dedicated 8,192-byte allocation can capture the
actual `q[z]` immediately after normalization/scaling, with unique writers
`j==0 && h<16` in packed-head mode. The CPU geometry proof verifies all 2,048
elements have exactly one writer and the last byte is 8,191. Do not recompute Q
in a separate diagnostic kernel or repurpose existing scratch/state. The
position/layer selector must default off; capture on/off state equality is a
required qualification because instrumentation can change compiler lowering.

## Reproduction and retention

Run from the repository root:

```bash
python3 experiments/own-xpu-runtime/research/continuation-2026-10-25/reference/analyze_reference.py
python3 -m unittest discover -s experiments/own-xpu-runtime/research/continuation-2026-10-25/reference -p 'test_*.py' -v
```

Seven CPU tests pass, including strict teacher-forced row validation, terminal-row
exclusion, the exact FMA residual, and the actual-input negative RMS control.
The result retains all original input/row hashes and external diagnostic hashes.
Historical evidence and native code remain unchanged.

The small embedding/conv fixtures are retained here. Larger state/y extraction
files are local generated fixtures, ignored by Git. Their raw authoritative
bundle is already in the independently verified
[PP archive](../../review-2026-10-25/durable-archives.json); extract
`pp2-v2/stage0/native/state-2147483647` and pass `--dump` to rerun if `/dev/shm`
is cleared. The CPU source/library build under `/dev/shm/llref` is an external
prerequisite with hashes, not a new portable CPU-oracle release. The original
reference tool and patches remain in
[e-reference](../../../gsq-rco-iq3s/service-speed/e-reference/RESULT.md).
