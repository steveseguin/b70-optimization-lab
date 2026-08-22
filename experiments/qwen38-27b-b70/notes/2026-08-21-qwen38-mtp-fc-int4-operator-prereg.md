# Qwen3.8 MTP `fc` INT4 eager-operator preregistration

Date: 2026-08-21

Status: **Q1 COMPLETE 2026-08-22 — PASS** (`qualified-only-for-default-off-integration-design`); see the [result](2026-08-22-qwen38-mtp-fc-int4-operator-result.md). Authorized by explicit user go-ahead this session, after every drafted prerequisite was satisfied and frozen. The four
launch-dependency conditions below are all met: (1) the authorized host-wide
`xe` recovery completed with its full post-recovery gate
([recovery note](2026-08-22-measuring-host-xe-recovery-2.md)); (2) the
fresh-root GPU3 stock-health r2 published a supervisor-validated immutable
`gpu3-incumbent-control-health-pass` terminal on boot
`256bc838-c015-4c91-a8f9-363d281f7555`
([r2 pass](2026-08-22-qwen38-gpu3-incumbent-control-health-r2-result.md));
(3) the driver now carries the bounded per-arm process-group watchdog, live
GPU2 BDF/UUID rederivation, same-boot binding, immutable per-arm receipts, and
an enclosing campaign terminal; (4) the qualifier's
`CAMPAIGN_LAUNCH_AUTHORIZED` literal and the driver's unconditional `run`
block were deliberately edited out together, source-pinning the health
terminal (never a caller input), with the block tests rewritten to assert the
authorized contract. There is still no argument or environment-variable
override; authorization is a property of these exact frozen bytes.

The launch dependency order (all satisfied) was:

1. A separately authorized, host-wide recovery of the `xe` driver for all four
   B70s must complete under the prerequisites and post-recovery gates in
   [local operations](../../../docs/local-ops.md). This note does not authorize
   that recovery, a GPU reset, or FLR.
2. After recovery, a newly preregistered GPU3 stock-control health diagnostic
   must use a fresh root and publish an immutable, supervisor-validated
   `gpu3-incumbent-control-health-pass` terminal. The stopped pre-recovery
   diagnostic is not eligible; see its
   [result](2026-08-21-qwen38-gpu3-incumbent-control-health-result.md).
3. Only after that new passing terminal is frozen may a future implementation
   add the missing bounded per-arm process-group watchdog, exact GPU2 BDF/UUID
   discovery, and immutable supervisor/watchdog receipts and enclosing campaign
   terminal/inventory for hangs, signals, and pre-arm failures. The exact new
   health-terminal path and SHA must be source-pinned and same-boot-bound rather
   than accepted as a replaceable caller input.
4. The driver and qualifier must then be deliberately edited together to remove
   both unconditional launch blocks. Those source changes require independent
   review, new CPU/adversarial tests, a focused commit, and new SHA-256 pins in
   this note. The current hashes cannot authorize a run.

Until all four conditions are satisfied, `check` is at most a read-only
identity diagnostic and `run` must fail before creating a result root.

## Frozen implementation identity

The only current implementation inputs are:

- [qualifier](../scripts/qwen38_mtp_fc_int4_operator.py), SHA-256
  `47f7a627c82354780b7f19452bbad397bd39cca0a5167308c379101817b57269`;
- [driver](../scripts/run-20260821-qwen38-mtp-fc-int4-operator-abba.sh),
  mode `0755`, SHA-256
  `a60e9a97236c1982cd6d735e3696122671db9fb613d23a12bf05014970591b4c`;
- [CPU tests](../scripts/test_qwen38_mtp_fc_int4_operator.py), SHA-256
  `06035ad81b1cb7e732caacccbe65e0cf9358331740f9c12d1a60ecb92e34d3ff`.

The pre-authorization frozen bytes were qualifier
`228da7aa46b6521e253a8507265192a529b786a09c3f885cd4d63a50c17beca9`, driver
`d62878ef573b136b7e8b1e6e5cbe199ccd04dea3a8ea6d12d021732c84af48f3`, and CPU
tests `4f0a3faadffe819c3038fedd91a927bbcb0a1a58e5212f7f8cf5a3b126f7e190`;
those three are the design-artifact identity and no longer authorize a run.

CPU validation covers import isolation, strict JSON and packet schemas, cache
inventory corruption, same-boot health-terminal binding, exact marker suffixes,
deleted-library rejection, the 20-file stage graph, M6/serial-M1 row equivalence,
ABBA ordering, runtime/cross-process stability, bootstrap/hurdle edge cases,
the direct-qualifier block, and the driver block-before-root guarantee. It does
not yet test the future watchdog, BDF discovery, or campaign terminal because
those launch components do not exist. Static checks do not establish XPU
numerical correctness, runtime engagement, timing, host health, or endpoint
behavior.

The eager control and candidate use the deployed composite extension
`/home/steve/staged-xpu-commitfix-graphfa-composite-20260820/vllm_xpu_kernels/_xpu_C.abi3.so`,
SHA-256
`4dd336013d155aab004fb1c916118957cb9349b491938da65769f2d8af18ffb0`.
The run packet requires Python `3.12.13` and Torch `2.11.0+xpu` and requires
one identical recorded runtime identity across all eight hypothetical arms.
Before launch authorization, the future driver must additionally freeze the
relevant Torch/XPU/oneDNN dependent-library bytes rather than relying only on
these version strings.
The preflight also binds the pinned GPU3-health supervisor validator, requires
the exact extension path as the first `PYTHONPATH` stage, requires its package
directory first in `LD_LIBRARY_PATH`, and corroborates the uniquely mapped
extension through `/proc/self/maps`, rejecting deleted mappings. It also
rederives the complete 20-file stage graph manifest, SHA-256
`47861e8391b6b25dd9c3eb25e25c5939753aa470858b667d5bdf181344db18da`.

## Bounded question

The screen asks whether replacing the live FP16 TP-local `mtp.fc` matrix
multiplication with the existing eager oneDNN W4A16 operator is numerically
valid, stable, and fast enough to justify designing a default-off integration
patch. It does not test vLLM, `torch.compile`, XPU graph capture/replay, oneCCL,
real concurrent TP2, MTP acceptance, endpoint quality, or end-to-end tokens per
second.

The production source path is Qwen3.5/3.8 MTP `fc`: a bias-free
`ColumnParallelLinear(10240, 5120, gather_output=True)` whose TP2 weight loader
slices output rows. Although the serialized tensor is BF16, the live server
loads the parameter as FP16. The qualifier must therefore preserve this exact
order:

```text
full BF16 tensor -> TP output-row shard -> FP16 live shard -> FP32 pack math
```

Quantizing the full tensor before slicing, quantizing directly from BF16, or
casting the full tensor before selecting the shard is a different experiment.

## Model, shard, and packing identity

The source file is
`/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan/model_extra_tensors.safetensors`,
SHA-256
`94102b67c6b84e65dbb9bae37c00bd88ac1a43ff577ce65fd8842d231c7e89de`.
The tensor is `mtp.fc.weight`, serialized BF16, shape `[5120, 10240]`, with raw
logical tensor SHA-256
`4eee377b67ec2122cf214dbe6946d16261873441f1851d64409d9c7566bb20cc`.

The two output-row shards are frozen independently:

| TP rank | Rows | BF16 shard SHA-256 | live FP16 shard SHA-256 |
| --- | --- | --- | --- |
| 0 | `[0, 2560)` | `1757625239f6436af83d61a2353b4f406ae1eef22ac1828b03d6cbbe2913d5ed` | `6cea656bf5e4d0683dff2a1e65b9c822d62fdb63d8510439afb9cf26d00ccc4b` |
| 1 | `[2560, 5120)` | `31ee2a7fc864ce05e3263257df7a7a11a0326b90c49c0868807324bce48241ed` | `7237258ded520195d2e22c4d7a2a6d4c8e0a54158d1bb992d4c9d0701c48395b` |

Packing is symmetric group-128 along K. For every group, nonzero scale is
`amax / 7`; values are rounded and clamped to signed `[-8, 7]`, shifted by
zero point eight, and eight consecutive K nibbles are stored least-significant
first in one `int32`. Contiguous backing storage is `[N, K/8] = [2560, 1280]`.
The logical oneDNN qweight view is `[K/8, N] = [1280, 2560]` with stride
`[1, 1280]`; FP16 scales are contiguous `[K/128, N] = [80, 2560]`; qzero is
scalar INT8 value eight with SHA-256
`beead77994cf573341ec17b58bbf7eb34d2711c993c1d976b128b3188dc1829a`.

The exact packed identities are:

| TP rank | packed backing SHA-256 | logical qweight SHA-256 | FP16 scales SHA-256 |
| --- | --- | --- | --- |
| 0 | `da795b5a921bd14f0d3ae814dab268199ccb88aa16bf1aa69ec27b51a7dfda79` | `adef7804c30b41794ba89e6fbcec88d14020db5760b4020e8d313a71160fab7a` | `c71498b300127c358d59166fb3380ad58871c700c7c077f81ebd6ff32359cb3b` |
| 1 | `8eda2db1e4aef2d5e0d711730973b23199a0f27daff7160f43c0c140cda9b03b` | `79b7f43a70342916d21229a474844fc4ba4eaeafad08247e45c70f6d1ae013f8` | `42594dc0dac733bc2e6044f7cc4b09090087eb82e08e811c5fcea11df9c48986` |

Both real shards contain zero all-zero groups. That observation does not relax
the format contract. A synthetic all-zero group must use finite positive scale
`1.0`, store nibble `8`, and independently decode to exact zero. The nibble
sentinel and zero-group test must pass before model packing; every real scale
must be finite and positive.

## Runtime and engagement contract

The future eight arms are intended to run sequentially on physical GPU 2,
exposed alone as logical `xpu:0` with `ZE_AFFINITY_MASK=2`. The qualifier now
requires the expected B70 name and UUID
`868023e2-0000-0000-4300-000000000000`; `0000:43:00.0` remains context until a
future driver rederives and binds the live BDF after recovery. TP rank here
means which frozen output-row shard is tested; this is not concurrent TP2
execution. The intended immutable global fresh-process order is:

```text
rank0-A1 FP16 control
rank0-B1 W4A16 candidate
rank0-B2 W4A16 candidate
rank0-A2 FP16 control
rank1-A1 FP16 control
rank1-B1 W4A16 candidate
rank1-B2 W4A16 candidate
rank1-A2 FP16 control
```

Processes may not overlap, and all must come from one host boot. Controls call
direct eager `torch.nn.functional.linear`. Candidates call direct eager
`torch.ops._xpu_C.int4_gemm_w4a16` with `bias=None`, group size 128,
`g_idx=None`, and the final ABI argument `input_dependency=True` explicitly.
Every process starts with
`VLLM_XPU_ONEDNN_INT4_COMPLETION_BARRIER=1` before importing torch.

Every candidate stderr must contain exactly one occurrence each of:

- `VLLM_XPU_ONEDNN_INT4_INPUT_DEPENDENCY reached`;
- `VLLM_XPU_ONEDNN_INT4_COMPLETION_BARRIER reached`.

Controls require zero occurrences. Both roles require zero determinism-pad
markers because M1 and M6 are outside that pad branch. A source symbol, an
environment value, or a mapped DSO without these runtime cardinalities is not
candidate engagement.

The qualifier snapshots the protected production TorchInductor compile-cache
root before imports and requires identical paths, file contents, sizes, and
mtime values after every arm and during later validation. Modes, ownership,
inodes, ctime, and directory metadata are not part of this inventory. It sets
`PYTHONDONTWRITEBYTECODE=1`, never
calls `torch.compile`, never captures an XPU graph, and never starts vLLM. This
gate supports only the bounded statement that the protected production
compile-cache roots did not change. oneDNN may still create process-local
primitive or JIT state during warmup.

## Correctness and stability gates

Fixtures are deterministic CPU-generated normalized FP16 inputs at exact
`M=1` and `M=6`, `K=10240`, `N=2560`. The controls are checked against an
independent CPU FP32 multiplication using the live FP16 shard. The candidates
are checked against a separate CPU FP32 multiplication using a fresh unpack of
the stored nibbles, stored FP16 scales, and qzero. Candidate difference from
the original live-FP16 oracle is recorded as quantization drift, not used as a
claim of original-model equivalence.

For both M values and every arm:

- all values must be finite;
- the selected oracle must pass `atol=0.02, rtol=0.01`;
- 32 synchronized eager replays must have one exact output digest;
- a deterministic input mutation must change both input and output digest and
  pass a newly derived selected oracle;
- for M6, the batched output must be bit-exact to concatenating six serial M1
  calls over the same six fixture rows.

Controls must reproduce exactly across A1/A2, candidates across B1/B2, and
their mutation outputs must reproduce within role. Inputs and both CPU-oracle
digests must remain identical across all four arms of a rank. Any discrepancy
is terminal; no tolerance or fixture may be changed after observing it.

## Timing, bootstrap, and decision gates

Only correctness-valid work is timed. Each shape receives 20 untimed warmup
calls followed by 40 XPU-event samples of 100 calls each. Candidate timing
therefore includes the explicit input dependency and completion publication
needed before a downstream consumer. Host wall time is not the primary clock.

The comparison uses fixed-seed, 10,000-iteration within-arm resampling of the
raw samples. For each rank and shape it reports A1-minus-B1, A2-minus-B2, and
their combined mean distribution with separate 95% confidence intervals. The
seed is `38,500,000 + 100 * tp_rank + M`.

Every condition is conjunctive on both output-row shards:

- M1: both observed paired savings and their central mean are nonnegative;
  both pairwise and the combined bootstrap 95% lower bounds are also
  nonnegative;
- M6: both observed paired savings are strictly greater than
  `17.092 us/call`; both pairwise bootstrap 95% lower bounds are greater than
  zero; and the combined bootstrap 95% lower bound is itself strictly greater
  than `17.092 us/call`.

`17.092 us/call` is a strict hurdle, not an equality pass. Across five MTP
calls it represents only `85.46 us` per target step, so even a pass cannot by
itself establish or plausibly account for the full move from the current
roughly 101 tok/s lane to 105 tok/s.

Any identity, health, cache, model, cast-order, packing, zero-group, mapping,
ABI, marker, finite-value, oracle, mutation, row-equivalence, replay,
cross-process, timing-schema, ABBA-order, bootstrap, M1, or M6 failure must stop
the future campaign. The current qualifier publishes an immutable invalid
packet only when it regains control from a managed operator exception; it does
not protect a hang, signal, or pre-arm driver failure. This is why a reviewed
external process-group watchdog and campaign terminal are mandatory before
authorization. A future failure must preserve its fresh root, run no later arm,
perform no same-root retry, and must not tune tolerances, samples, seeds, or the
hurdle. Eight valid arm packets would be required before comparison.

## Interpretation and later integration boundary

A failed correctness or stability gate rejects this exact operator use. A
numerically valid result that misses any timing gate rejects it as a speed
lever. Infrastructure or health failure is invalid evidence, not a numerical
pass or rejection. A complete pass qualifies only the idea of preparing a
separately reviewed, default-off, model-specific integration patch.

Integration is a new experiment. It must, at minimum:

- retain the live BF16-shard-to-FP16 load semantics and bind the packed buffers
  to this exact `mtp.fc`, rather than globally changing unquantized linears;
- preserve `input_dependency=True` and completion publication before TP2's
  cross-rank gather consumes the shard output;
- register any new environment selector in vLLM's `envs.py` so it participates
  in `envs.compile_factors()`;
- use a distinct fresh persistent compile-cache identity rather than reusing
  the sealed `b991`/`f358` artifacts;
- account for live FP16 plus packed-buffer VRAM if both are retained;
- pass separately preregistered eager, compile, graph, real concurrent TP2,
  MTP-acceptance, target-token, quality, and endpoint-throughput gates.

This blocked design authorizes no local endpoint run, no full-25
suite, no model/source integration, no vLLM cache build, no LocalMaxxing
submission, and no workload or change on the other computer. In particular,
it does not authorize SSH or remote GPU use on the two-B70 reference host
`steve-TURIND8-2L2T`.

## Future sequence — disabled pseudocode only

The following is deliberately non-executable. It records order, not commands:

```text
# DISABLED: obtain separate authorization for host-wide all-four-B70 xe recovery
# DISABLED: execute docs/local-ops prerequisites, recovery, and complete post-gates
# DISABLED: preregister a new GPU3 stock-health run with a never-used root
# DISABLED: freeze a supervisor-validated immutable GPU3 PASS terminal and SHA
# DISABLED: add the bounded arm supervisor, exact device discovery, and terminal
# DISABLED: source-pin the exact same-boot GPU3 PASS terminal path and SHA
# DISABLED: edit out both qualifier and driver run blocks in tracked source
# DISABLED: rerun CPU/static review and freeze new qualifier/driver/test/doc hashes
# DISABLED: commit and push clean main; require local main == origin/main
# DISABLED: select a never-used operator result root
# DISABLED: run rank0 A-B-B-A, then rank1 A-B-B-A on physical GPU2
# DISABLED: stop on the first invalid/nonzero arm; otherwise compare all eight
```

## Q1 launch commands (authorized 2026-08-22)

```bash
cd /home/steve/llm-optimizations
d=experiments/qwen38-27b-b70/scripts/run-20260821-qwen38-mtp-fc-int4-operator-abba.sh
"$d" check
"$d" run /home/steve/qwen38-mtp-fc-int4-abba-20260822-r1
"$d" compare /home/steve/qwen38-mtp-fc-int4-abba-20260822-r1
```

The health terminal is source-pinned in the driver and qualifier; `run` and
`check` take no health argument. Same-boot binding, four-B70 discovery, GPU2
UUID, and the 900s per-arm watchdog are enforced at launch. On the first
invalid or nonzero arm the campaign stops, preserves its fresh root, writes a
`failed` campaign terminal, and performs no same-root retry.
