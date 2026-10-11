# Closed arithmetic-definition arm

| Arm | Evidence and outcome | Revisit condition |
| --- | --- | --- |
| arithmetic identity defined by a platform libm | v1 same-device kernels matched 72/72, but device/host core matched only 50/72; first real-model step matched 0/48 states despite 8/8 tokens. Explicit compiler flags did not define elementary-function bits. [Explanation](README.md). | Do not use a platform library name as a portable bit-level identity. A new path needs fixed operations/constants, host compiler equality, exhaustive elementary device gates and real-model state checks. |

Packet17 v2 is a candidate arithmetic identity. Neither a successful native
compile nor matching host fixtures closes its pending device proof obligations.

| offload precision options only on the compile line | [Same-object link A/B](evidence/20261011-wb-a-link-flags/README.md): plain link differs for log-v2 at 0x3f7ffffe; precise link matches all 2^32 inputs for exp-v2 and log-v2. | Both options must be on compile and link commands; generated-link assertion and fresh device gates required. |
