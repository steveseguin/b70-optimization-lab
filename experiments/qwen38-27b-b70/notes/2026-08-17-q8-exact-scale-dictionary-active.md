# Qwen3.8 Q8 exact scale-dictionary arm

Date: 2026-08-17  
Status: **active; claimed on the ASRock two-B70 host**  
Scope: target-only Q8_0 TP2, F16 KV, no MTP/DFlash/speculation

## Hypothesis

The reordered Q8_0 hot path stores 32 signed quantized bytes and one FP16
scale per block. The earlier lossless-packing audit tested the 32 Q values and
found no practical fixed-width win. This arm changes only the scale plane.

A complete streaming scan of the exact promoted model found:

- 498 Q8_0 tensors;
- 840,417,280 Q8_0 blocks;
- 1,462 distinct positive FP16 scale bit patterns;
- scale bit patterns from `0x0001` through `0x2204`;
- 11 bits are sufficient for an exact model-wide dictionary index.

An 11-bit index changes the ideal reordered block traffic from 34 bytes to
33.375 bytes, a `1.838235%` reduction before dictionary overhead. A 2,924-byte
read-only dictionary per reordered tensor is negligible for the large hot
matrices and should remain cache-resident. Every scale is reconstructed to
its original FP16 bits before the existing multiply, so the arithmetic and
quality target are unchanged.

## Guardrails

- This is model-specific research, not a generic Q8 file-format change.
- Reorder must fail closed if a scale is absent from the exact dictionary.
- The treatment must live in a separate source/build tree and remain off in
  the accepted reproduction.
- First gate: bounded load plus `p0/n1`, exact token and no Xe fault/reset.
- Second gate: fixed 128-token oracle hash plus an explicit poison/liveness
  proof that the packed decoder executed.
- Performance gate: same-binary or otherwise position-balanced A/B/B/A at
  `p64/n256/r3`; reject a result inside ordinary run noise.
- Only a repeatable, quality-clean gain proceeds to the 12-prompt cache-zero
  endpoint suite and semantic/long-context canaries.

## Expected ceiling

If decode scaled perfectly with bytes, the accepted `36.772932 tok/s` result
would rise only to about `37.46 tok/s`. Bit unpacking and the dictionary lookup
can consume that gain, so a neutral or negative result is plausible. This arm
cannot by itself reach 40 tok/s; its value is testing a previously unmeasured,
exact bandwidth reduction rather than repeating flag or Q-value packing work.

