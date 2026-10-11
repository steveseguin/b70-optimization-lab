# Closed arithmetic-definition arm

| Arm | Evidence and outcome | Revisit condition |
| --- | --- | --- |
| arithmetic identity defined by a platform libm | v1 same-device kernels matched 72/72, but device/host core matched only 50/72; first real-model step matched 0/48 states despite 8/8 tokens. Explicit compiler flags did not define elementary-function bits. [Explanation](README.md). | Do not use a platform library name as a portable bit-level identity. A new path needs fixed operations/constants, host compiler equality, exhaustive elementary device gates and real-model state checks. |
| host reference math while holding the W-A card | Up to 600 CPU seconds per function occupied a device window. References now come from sealed, bounded lossless slabs with the same inputs and ULP output. | Keep reference generation and readback in CPU preparation; measure device/streaming time only after admission. |
| offload precision options only on the compile line | [Same-object link A/B](evidence/20261011-wb-a-link-flags/README.md): plain link differs for log-v2 at 0x3f7ffffe; precise link matches all 2^32 inputs for exp-v2 and log-v2. | Both options must be on compile and link commands; generated-link assertion and fresh device gates required. |
| GNU native-math references for the Intel W-A twin | [CPU-only finite expf mismatch](evidence/wa-gnu-reference-diagnostic.md): input 0xbe27ffff differs by one bit. The unsealed GNU pass is preserved. | Use the original Intel host flags without -mfma for generator and verifier. W-B detmath hashes are independent and unchanged. |

Packet17 v2 is a candidate arithmetic identity. Neither a successful native
compile nor matching host fixtures closes its pending device proof obligations.
