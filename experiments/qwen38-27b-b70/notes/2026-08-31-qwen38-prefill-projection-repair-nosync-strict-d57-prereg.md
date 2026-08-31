# D57 preregistration: no-barrier strict qualification

Date: 2026-08-31

This run is preregistered after two D56 processes produced byte-identical
64-layer traces and complete responses, and before the four-process D56 screen
finishes. D57 is authorized only if D56 remains exact 4/4.

D57 uses the D54/D55 strict protocol and the same M=512 projection padding, but
sets `VLLM_XPU_QWEN38_PREFILL_PROJECTION_SYNCHRONIZE=0`. All twelve token-ID
sequences must equal the synchronized D54 reference, cached tokens must be zero,
all workload and canary gates must pass, and the fault/shutdown audit must be
clean.

The primary decode metric remains the median of prompt-class medians. The
optimization target is prefill/TTFT: compare the full-suite TTFT distribution
against D54's synchronized median of 380.687002 ms, without selecting a best
prompt or extrapolating. A pass makes no-barrier stream ordering the preferred
TP1/MTP0 correctness baseline; TP2 and speculative decoding still require
their own strict qualification.
