# Laguna exact dequant-MAD on the GRF128 transposed-scale route

Date: 2026-07-31 America/Toronto

Status: **preregistered static and component screen; no endpoint authorized.**

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
