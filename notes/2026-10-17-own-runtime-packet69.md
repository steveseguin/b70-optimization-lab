# Packet 69: rank 1 outside the layers

## Measurement screen ready (CPU only)

Rank 1's head was excluded by packet64's recorder. Packet69 copies the frozen
packet64-attribution sources and adds `logits`, `final.*`, and `argmax` to the
observation filter. Arithmetic and all inherited numerical objects are
unchanged. No GPU, model load, service or host setting was used.

The original 2.94 ms remainder is a **scaled estimate** of the host half minus
its measured device layer span. Existing receipts cannot split the missing
head, final HC and argmax. The new report measures those parts and retains
transfers plus a named residual for host submission, waits, gaps and other
unobserved work. That residual is not GPU idle.

The GGUF head is Q6_K: 521,472,000 stored bytes, 248,320 rows × 2,560 columns.
Production expands each row to 3,200 bytes (int8 values plus F32 scale/16),
so it reads 794,624,000 resident weight bytes. The 91,392-row draft prefix
reads 292,454,400 resident bytes. Its existing raw time is **521.30 µs,
561.0 GB/s**; the scaled 510.45 µs estimate implies 572.9 GB/s. Using GGUF
bytes gave the misleading 376 GB/s estimate. At 540–590 GB/s the resident
prefix floor is 495.69–541.58 µs. Target-head time remains unmeasured.

[Existing-data analysis](../experiments/own-xpu-runtime/stage2/packet69-rank1-head/evidence/existing-analysis.json)
retains the full source hashes and raw/scaled distinction.

The instrumented GNU host and device builds pass. Only the entry translation
unit was rebuilt; numerical objects are inherited by hardlink. Four small
observer runs (two each under GNU and Intel host compilers) agree, and the
native source comparison matches packet64-attribution except the observer
filter/category header. These are small CPU checks, not CPU model runs or a
replacement for the device oracle. All 91 wrapper checks pass, including
post-drain report failure, retained markers on real drain/postflight failure,
and lane-B planning. Five inherited attribution validator checks pass.

The copied wrapper incorporates packet70's release sequence: save checked
request inputs, drain, confirm worker exit/device isolation/postflight, release
both lane locks, then aggregate on CPU. A report failure cannot retain the
lane marker or create a device-fault latch. Packet49 remains the output oracle.

[Coordinator command](../experiments/own-xpu-runtime/stage2/packet69-rank1-head/WINDOW.md).
Candidate preparation follows in `candidates/`; this measurement selection
and its bound sources remain unchanged after publication.
