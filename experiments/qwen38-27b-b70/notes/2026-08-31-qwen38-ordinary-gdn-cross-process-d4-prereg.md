# Qwen3.8 ordinary native-GDN cross-process D4 preregistration

Date: 2026-08-31

Status: **preregistered before D4 operator calls**

## Question

INT4 GEMMs, the padded FP16 B/A path, and Gemma RMSNorm are now stable at all
actual MTP0 row counts. Is the complete ordinary native XPU GDN transition
bitwise stable across fresh processes, including its recurrent state?

## Frozen diagnostic

- exact current image ID
  `sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136`;
- local B70 GPU 0; four fresh containers; TP1 production dimensions from the
  pinned model config; FP16 activations/conv state and FP32 SSM state;
- every strict prefill M (`48,49,52,53,55,56,57,59,65,71,75,78`), followed by
  32 fixed M=1 ordinary decode transitions from the produced state;
- complete prefill core/z/conv/SSM hash and complete decode trajectory plus
  final conv/SSM hash;
- repeat the entire zero-state chain twice inside each process, then compare
  SHA-256 across all four fresh processes.

Any prefill or decode/state mismatch is a positive causal finding. Full
bitwise equality is negative evidence only. This diagnostic uses no model
weights and cannot promote endpoint quality or speed.
