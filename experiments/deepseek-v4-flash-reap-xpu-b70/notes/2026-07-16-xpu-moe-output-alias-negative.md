# XPU modular-MoE output-alias negative

Date: 2026-07-16

## Question

Can the modular-MoE path avoid copying the routed-expert result from its common
workspace into a separate output tensor before the shared-plus-routed add?

## Candidate

vLLM commit `8007ee686b1bf4cefeef2507731bf048cd778eda` adds the default-off
`VLLM_XPU_MOE_OUTPUT_ALIAS=1` guard. On XPU, it aliases the final routed output
to the common workspace only when shape, dtype, device, contiguity, and empty
workspace contracts all match.

Evidence:

- `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/mtp1-moe-output-alias-candidate-20260716T0130Z`
- record control identity: `mtp1-m2-fusion-candidate-20260716T000928Z`

## Result

- Correctness: 10/10 exact capture suites; every request remained cached-zero.
- Strict screen: `57.204014 tok/s` median, `53.917766` p10.
- Independent confirmation: `56.198992 tok/s` median, `53.606565` p10.
- Qualified record/support: `57.412142/56.952065 tok/s`.

The candidate did not improve the qualified record and the confirmation was
below its support run. It is therefore a noise-floor negative, not a record.

## Interpretation and decision

The apparently redundant copy is not a useful end-to-end target in the current
reusable-graph lane. Allocation is amortized during graph construction, while
aliasing changes workspace/cache lifetime without removing enough replay work
to survive full-model variance. Keep the implementation default-off for future
composition experiments, but do not enable it in the production identity and
do not submit it to LocalMaxxing.
