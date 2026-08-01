# Laguna exact dequant-MAD on the GRF128 transposed-scale route

Date: 2026-07-31 America/Toronto

Status: **closed at the component gate; exact but performance-neutral.**

## Evidence and hypothesis

The current exact BF16-KV record is `125.4619731637751 tok/s`
conventionally. Its 1,609 verifier cycles emitted 6,356 tokens, or
`3.950279676817899` emitted tokens per cycle. The derived median cycle is
therefore about `31.486 ms`; reaching 130 at unchanged acceptance requires
about `30.387 ms`, a saving near `1.10 ms` per verifier cycle.

The target executes one INT4 W13 and one INT4 W2 grouped GEMM in each of 48
layers. On the current GRF128 transposed-scale component, those two shapes sum
to roughly `0.50 ms` per layer. A genuine 4--5% grouped-GEMM improvement is
therefore large enough to matter at the endpoint.

The existing exact dequant-MAD treatment removes the INT4 dequantizer's BF16
`-136` add and folds that bias into the following BF16 scale operation. It was
tested on the older 256-GRF, checkpoint-scale-layout route and did not improve
the endpoint. The current record is materially different: it uses 128-GRF
occupancy and contiguous `[expert,K/32,N]` scale storage, but the launcher
explicitly disables both whenever dequant-MAD is selected. That old negative
does not measure this combination.

## Frozen treatment

Screen the existing production template combination:

- `ScaleVec=true`;
- `DequantMad=true`;
- `TransposedScales=true`;
- BMG 128-GRF mode;
- policy `w4a16_policy_m_8`, group size 32.

If it passes, expose it through a separately named default-off exact-width-12
decode selector. The selector must require the current target-only M=12 route,
BF16 activations and scales, INT4 weights, total routed rows 120, group size
32, ordinary non-tile-major weights, and transposed scale layout. Prefill,
draft, selector-off, other widths, other policies, and the existing generic
dequant-MAD selector remain unchanged.

The arithmetic contract is the already proved dequant-MAD identity. The same
raw INT4 nybble, BF16 scale, BF16 destination rounding, DPAS inputs, and FP32
accumulation order must remain. No scale folding or relaxed comparison is
allowed.

## Gates and stop rules

1. Extend the durable IGC probe to instantiate the exact transposed-scale MAD
   combination. Under 128-GRF BMG code generation require two DPAS
   instructions, the expected BF16 MADs, no spill/scratch markers, and fewer
   total instructions than the current transposed-scale/non-MAD control. Stop
   if static register allocation or spills defeat the premise.
2. Only after the static pass, implement a separately named kernel and
   fail-closed selector in a fresh source branch. Inspect the exact diff and
   final production ELF before device execution.
3. Run the existing deterministic changed-input component on one healthy B70
   for W13 (`M=120,N=2048,K=3072`) and W2
   (`M=120,N=3072,K=1024`). Require raw-BF16 equality on every output, no
   shape regression greater than 1%, and at least 3% improvement in the
   summed stable median. A smaller result stops before a model service because
   it cannot credibly close enough of the 130-tok/s gap.
4. A component pass authorizes a new endpoint preregistration; it does not
   itself authorize a score. Any later endpoint must retain the current model
   revisions, BF16 KV, width 12 / DFlash 11, one active generation, fixed cold
   suite, canonical q1 teacher, cache-zero policy, 146/145 target and 14/13
   draft topology, first-valid-score rule, and clean pre/post idle gates.

No target/draft/KV precision change, teacher change, prompt change, warmed
generation, retry, metric substitution, reset, reboot, or privileged recovery
is authorized by this screen.

## Result

The static screen passed but the device component stopped the treatment.

- Candidate source:
  `daa9e94f9dab4a52f655d54f9a87483aa941fd2e`.
- Candidate DSO SHA-256:
  `f3f736290f5e2aea3720b7aa920511d5eba4b301e7834a711468ae608b810cfd`.
- Frozen build artifact:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-dequant-mad-grf128-transposed-build-daa9e94-20260801T054606Z`.
- Corrected component artifact:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-dequant-mad-grf128-transposed-component-fixed-daa9e94-20260801T054721Z`.

The oneAPI 2025.3 build completed in `16:37.89`, peaked at `106,749,392`
KiB RSS, used no swaps, and linked against the expected `libsycl.so.8` ABI.
The BMG 128-GRF static probe retained two DPAS instructions and no spill
traffic while reducing the transposed kernel from 396 to 383 instructions.

Both component workers recorded the frozen 200 warmups per shape followed by
15 samples of 40 launches. The selector-off control and selector-on treatment
loaded the same candidate ELF and used identical transposed scales; only
`VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_MAD` changed.

| shape | control | treatment | speedup | raw BF16 exact |
|---|---:|---:|---:|---:|
| W13, `M=120 N=2048 K=3072` | 0.321024 ms | 0.321206 ms | 0.999432x | 3/3 |
| W2, `M=120 N=3072 K=1024` | 0.183683 ms | 0.183573 ms | 1.000596x | 3/3 |
| summed | 0.504707 ms | 0.504779 ms | 0.999856x | 6/6 |

This misses the preregistered 1.03 summed promotion threshold by a wide margin.
No model service, endpoint score, reset, or reboot followed. Exact dequant-MAD
on the GRF128 transposed-scale route is therefore closed unless new profiling
evidence changes the premise.

An earlier artifact at
`laguna-dequant-mad-grf128-transposed-component-daa9e94-20260801T054636Z`
has valid 6/6 exactness but **invalid timing evidence**: the gate parent parsed
the requested 200/15x40 protocol without forwarding it to its workers, which
therefore used the obsolete 8/9x20 defaults and reproduced the known W2
mid-series transition. The gate now forwards and records all timing arguments;
the corrected artifact above is the only performance evidence.

## Accounting clarification

The 6,356 figure above is the metrics-counter quantity `1,609` verifier drafts
plus `4,747` accepted draft tokens. It is useful for a median-rate-derived
cycle estimate but should not be described as an independently timed emitted
token count. The final record's aggregate suite accounting reports 6,354
output tokens over 52.014 seconds after TTFT, or about 32.327 ms per verifier
cycle. The endpoint requirement remains roughly 1.1 ms of average-cycle
savings at unchanged acceptance; neither estimate affects this component stop.
