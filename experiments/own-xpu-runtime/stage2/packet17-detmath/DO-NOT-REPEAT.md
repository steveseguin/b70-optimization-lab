# Closed arithmetic-definition arm

| Arm | Evidence and outcome | Revisit condition |
| --- | --- | --- |
| arithmetic identity defined by a platform libm | v1 same-device kernels matched 72/72, but device/host core matched only 50/72; first real-model step matched 0/48 states despite 8/8 tokens. Explicit compiler flags did not define elementary-function bits. [Explanation](README.md). | Do not use a platform library name as a portable bit-level identity. A new path needs fixed operations/constants, host compiler equality, exhaustive elementary device gates and real-model state checks. |

Packet17 v2 is a candidate arithmetic identity. Neither a successful native
compile nor matching host fixtures closes its pending device proof obligations.
