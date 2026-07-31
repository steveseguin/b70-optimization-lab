# Laguna INT4 full-pair SIMD32 dequant-MAD preregistration

Date: 2026-07-31 America/Toronto

## Premise

The exact `SCALE_VEC=1, DEQUANT_MAD=1` mainloop is 376 instructions in the
matched `w4a16_policy_m_8` BMG probe, versus 389 for SCALE_VEC alone. It still
lost about 1% in the earlier weak endpoint screen. The generated ISA explains
one avoidable cost: every channel pair is issued as two SIMD16 MADs, and IGC
places each high-half result in a temporary register before emitting 16 moves
per k-tile to assemble the full-GRF DPAS inputs.

The two FP32 channel scales and two FP32 MAD biases are adjacent in the
per-work-item arrays. Across the 16-lane subgroup they therefore form one
32-element scale operand and one 32-element bias operand. The dequantized BF16
channel pair is already one 32-element GRF. vISA supports SIMD32 elementwise
execution, so one `mad (M1, 32)` can express the same two independent SIMD16
MADs over those full-pair operands.

This does not combine lanes or change arithmetic. Element `i` still computes
the same `scale[i] * fragment[i] + bias[i]` into BF16, with the same operand
types and one final rounding. Only execution width and register presentation
change.

## Candidate

Starting from XPU-kernel commit
`46a88e09d96fe06871c87a23de534fb47f1e039b`:

- keep separate read-only fragment and write-only destination operands (the
  in-place experiment proved `+rw` is harmful);
- reinterpret each adjacent pair of per-work-item FP32 scales and biases as
  `cute::intel::storage_vector_t<float, 64>`;
- declare 32-element FP32 scale/bias operands and one 32-element BF16 source
  and destination; and
- replace the two `mad (M1, 16)` statements with one `mad (M1, 32)`.

No selector, model, weight, KV dtype, speculation policy, collective,
topology, teacher, prompt, or metric changes. The candidate remains reachable
only through the existing default-off `VLLM_XPU_LAGUNA_DEQUANT_MAD=1` path.

## Stage gates

1. Implement on a dedicated branch and run only the durable IGC mainloop probe
   first. Do not start a full extension build or touch a GPU endpoint yet.
2. Stop if the SIMD32 vISA form is rejected, if DPAS differs from 2, if the
   arithmetic is not exactly 32 BF16 MAD elements per k-tile, if spill/fill
   markers increase, if `mov` is not below the incumbent MAD's 156, or if
   total instructions do not improve on 376 by at least eight.
3. Only after the static gate passes, build the production grouped-GEMM DSO
   with the existing oneAPI/CMake/Ninja identity and preserve its hash.
4. Run the existing adversarial component exactness gate against both
   `DEQUANT_MAD=0` and the first two-SIMD16 MAD implementation. Require
   bitwise equality over every tensor and scale population. Stop on the first
   mismatch or runtime/device failure.
5. Only then mint a runtime lock and run one cold score on the exact 121.037
   BF16-KV stack with target 146/145 and draft 14/13. A first exact result in
   the noise band requires interleaved confirmation before promotion.

No reboot, reset, FLR, driver reload/unbind, shared-memory deletion, metric
window change, quality relaxation, teacher regeneration, retry after a failed
gate, or best-of-run selection is authorized.

## Expected value

If IGC lowers SIMD32 directly, this can remove up to 16 MAD issue slots and the
16 fragment-assembly moves per k-tile while retaining the exact fusion's
32-add elimination. It is one of the few remaining candidates that attacks
the measured dominant INT4 graph segment and has a cheap, decisive pre-GPU
test. It is not claimed to reach 130 tok/s alone.
