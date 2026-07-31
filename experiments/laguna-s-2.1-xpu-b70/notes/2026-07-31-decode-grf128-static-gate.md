# Laguna width-12 decode GRF128: production static gate

Date: 2026-07-31 America/Toronto

Status: **passed for a component test; no throughput claim yet**. The real
production BF16/INT4 `w4a16_policy_m_8` dispatcher emits one separately named
128-GRF kernel for the exact width-12 decode route and retains a matched
256-GRF control. No GPU process, model load, generation, score, reset, or
reboot occurred in this gate.

## Candidate identity

- kernel base: `46a88e09d96fe06871c87a23de534fb47f1e039b`;
- candidate: `e4163f93574326b2772742e0f51372a5a3777aa5`;
- branch: `experiment/laguna-decode-grf128-20260731`;
- compiler: oneAPI `icpx` 2025.3.3, BMG AOT backend;
- backend mode: `-cl-intel-enable-auto-large-GRF-mode`;
- artifact root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-decode-grf128-dispatch-20260731T0857Z`.

The dispatch is fail-closed. The new kernel requires BF16 activations and
scales, INT4 weights, R/C layout, non-tile-major `w4a16_policy_m_8`, group
size 32, `total_m == 120`, `SCALE_VEC=1`, `DEQUANT_MAD=0`, `SCALE_FOLD=0`,
and literal selector `VLLM_XPU_LAGUNA_DECODE_GRF128=1`. Width-12 verifier
rows times top-10 routes produce `total_m=120`. Draft (`total_m=10`),
prefill, selector-off, and every other policy use an explicit 256-GRF
property.

## Production device evidence

The probe included `grouped_gemm_xe2_interface.hpp` and instantiated the real
`MoEGEMMLauncher<'R','C',w4a16_policy_m_8>` rather than a reduced mainloop.
Device compilation and BMG AOT generation succeeded. The throwaway host
executable then failed to link because the probe intentionally did not link
PyTorch; that post-AOT host-link failure is not treated as a successful
runner exit, and it is not a device compile failure. The complete `.asm` and
`.zeinfo` outputs below were emitted before it.

| Property | GRF128 candidate | GRF256 control |
| --- | ---: | ---: |
| GRFs | 128 | 256 |
| EU threads | 8 | 4 |
| SIMD | 16 | 16 |
| IGC instructions | 6,174 | 6,134 |
| DPAS | 32 | 32 |
| `sync.allrd` | 217 | 225 |
| `sync.nop` | 261 | 213 |
| scratch metadata | absent | absent |

Every arithmetic, load/store, gateway/SLM send, barrier, branch, and data
movement mnemonic count is identical. The complete delta is eight fewer
`sync.allrd` and 48 more `sync.nop`, or 40 extra scheduling instructions in
the 128-GRF form. This is a real static cost, not hidden. It is small enough
to test because the requested mode doubles resident EU threads from four to
eight. No speedup is inferred from occupancy metadata alone.

The metadata inventory contains exactly the intended production GRF128
kernel plus a SYCL runtime memcpy wrapper at 128 GRFs. The matched production
control is explicitly 256 GRFs. All grouped-GEMM `parallel_for` sites were
audited: every non-candidate site supplies `grf_size<256>`.

## Build-headroom change

The candidate also removes the unused `DEQUANT_MAD=1, SCALE_VEC=0` template
instantiation. That combination was already rejected and is now explicitly
invalid: `DEQUANT_MAD=1` requires `SCALE_VEC=1`. This does not alter the
incumbent (`SCALE_VEC=1, DEQUANT_MAD=0`) but recovers compiler memory for the
separately named decode kernel.

## Gate decision

Proceed to a full DSO build, then changed-input component bitwise comparison
and topology/dispatch validation. Do not run the frozen endpoint score unless
those gates pass. If the component differs or the selected kernel is not
confined to the width-12 decode call, reject without scoring.

