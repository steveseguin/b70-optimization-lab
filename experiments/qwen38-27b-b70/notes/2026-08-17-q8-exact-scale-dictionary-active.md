# Qwen3.8 Q8 exact scale-dictionary arm

Date: 2026-08-17  
Status: **closed; not promoted**
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

## Result

The complete source-side codec simulation was exact over all 840,417,280 Q8
blocks. It also found a smaller structured dictionary than the initial global
count implied:

- 510 exponent-zero FP16 patterns;
- one shared set of 128 normal mantissas;
- exponents 1 through 8;
- 1,534 valid structured codes, with the exact model emitting at most code
  1,471;
- 1,276 table bytes per reordered tensor plus the 11-bit code stream.

The first GPU implementation used binary search only during one-time reorder.
It built successfully with oneAPI 2026.1.1 and completed a bounded TP2
`p0/n1` smoke at `34.906203 tok/s`. The fused-path verifier reported
`VERIFY_MISMATCH=0`, and both GPUs remained normal. This is not a performance
comparison: one cold token is only a safety smoke. A fixed CLI quality probe
then spent more than three minutes in serialized reorder/validation setup and
was stopped manually. It never reached generation, so this revision did not
earn quality clearance.

A direct 17 KiB encode lookup reduced that setup to about 18 seconds, but two
ownership revisions failed the safety gate:

1. A lookup cached by global device ID exited with host `SIGSEGV`; cross-device
   queue ownership was the likely fault.
2. A lookup allocated, used, synchronized and freed on each tensor's own queue
   avoided the host segfault, then failed the first prompt graph with
   `UR_RESULT_ERROR_INVALID_MEM_OBJECT` at `MUL_MAT` after 16.95 seconds.

Neither failure caused an Xe/GuC fault, reset, hang or abnormal XPU state. The
accepted source and binaries were never modified. No decode A/B, output oracle,
endpoint suite or LocalMaxxing submission was attempted after the safety gate
failed.

## Decision

Close this arm. Its ideal ceiling is only 1.84%, the hot decoder adds bit
unpacking and a table load, and the prototype changes an in-place tensor layout
that other reordered-Q8 consumers assume is a direct FP16 plane. A credible
retry must first provide explicit layout metadata and update every consumer,
or use a separately allocated packed plane with proven lifetime and queue
ownership. Do not retry either retained patch unchanged.

Retained source deltas:

- slow green-smoke revision:
  [`q8-exact-scale-dict11-slow-smoke-20260817.diff`](../patches/q8-exact-scale-dict11-slow-smoke-20260817.diff),
  SHA-256 `5a5cc9d104d002258859aac3c2680d580702ebf57f60067fc4769e1e3270a07c`;
- direct-lookup unsafe revision:
  [`q8-exact-scale-dict11-direct-lookup-unsafe-20260817.diff`](../patches/q8-exact-scale-dict11-direct-lookup-unsafe-20260817.diff),
  SHA-256 `773889bc41c9704c99c98ea366fdc4127c026f4d5d5ba145efb0ea29ad88a661`;
- structured summary:
  [`2026-08-17-q8-exact-scale-dictionary-negative.json`](../data/2026-08-17-q8-exact-scale-dictionary-negative.json).

Local raw evidence remains under
`/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260817-scale-dict11/`.
