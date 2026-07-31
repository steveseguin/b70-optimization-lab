# Laguna exact decode mainloop specialization preregistration

Date: 2026-07-31 America/Toronto

Status: **static/source experiment authorized; no endpoint score authorized**.

## Premise

The valid width-12 target decode call has a frozen arithmetic identity:

- BF16 activations/scales and packed INT4 weights;
- row-major A, column-major B, non-tile-major output;
- `w4a16_policy_m_8`, `total_m=120`, quantization group size 32;
- `SCALE_VEC=1`, `DEQUANT_MAD=0`, `SCALE_FOLD=0`.

The current separately named GRF128 kernel still calls the generic
`MoEGEMM` entry with runtime booleans and group size. Its device body therefore
contains the folded, MAD, vectorized, and incumbent scale mainloops for each of
four group sizes. The production BMG image is 6,174 instructions despite the
isolated live mainloop being only hundreds of instructions.

## Treatment and control

Add a second separately named default-off kernel selected by
`VLLM_XPU_LAGUNA_DECODE_EXACT_SPECIALIZED=1`. It is eligible only when the
already verified GRF128 selector and every identity predicate above are true.
Within `MoEGEMM`, a compile-time specialization must directly instantiate
`xe_gemm_4bits<...,32,false,false,true,false>` and omit all runtime scale-path
and group-size branches. The common expert scheduler, atomic ordering,
workgroup mapping, loads, stores, DPAS mainloop, BF16 rounding, and output
topology remain unchanged.

The matched control is the valid `e4163f935` GRF128 kernel with the new selector
off. Draft, prefill, other policies, other group sizes, selector-off calls, and
the 256-GRF fallback must be byte/source-identical to that control.

## Stop gates

1. Compile only the real production dispatcher for BMG and compare the new
   named kernel with the existing GRF128 control.
2. Stop before a full DSO build unless the specialized kernel reports 128
   GRFs, no scratch/spill metadata, unchanged DPAS and live BF16 arithmetic
   counts, and a material reduction in instructions or dependency barriers.
3. Audit all `parallel_for` sites and generated kernel names. Stop if the new
   selector can affect draft, prefill, another policy, group size, or the
   selector-off control.
4. Only after a static pass, build the DSO and require changed-input raw-BF16
   equality against the GRF128 control for both real W13/W2 shapes.
5. Endpoint authorization requires a separate note after the component gate.
   The frozen 13-prompt teacher, cache-zero, 146/145 target, 14/13 draft,
   one-generation, no-warmup, no-retry contract remains authoritative.

No reboot, reset, driver action, quality/metric change, teacher regeneration,
or score-bearing GPU run is authorized by this preregistration.

