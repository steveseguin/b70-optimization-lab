# Packet74 boundaries

| Arm or assumption | Evidence / next condition |
| --- | --- |
| Restore historical packed kernel verbatim | Packet9→10 head+final-HC5.47→2.19 ms; new register-only packed loading is required. [History](../../../../notes/2026-10-17-own-runtime-packet74.md). |
| Claim317.85 MB net head saving | Omits308.90 MB unchanged draft prefix. Actual allocation delta8.94 MB. [VRAM](VRAM.md). |
| Expanded-only allocation or stride used for packed dispatch | Different physical formats; packet74 loader replaces storage and uses210/34-byte blocks. CPU fixtures cover both alignment phases and17 rows. |
| GPU speed inferred from smaller weights | Not measured; unpacking ALU and geometry can outweigh traffic savings. Coordinator microbenchmark and both-lane screens required. |
| Dense view claimed to cover every dense tensor | Scope is explicitly listed; fused HC/small-FFN and raw matrices stay unchanged. |
| Lane B before complete exact A / selected slower than either control | Refused by best.py/winner.py; fixed ties, no retries. |
| CPU preparation called device qualification | [Closeout](CPU-PREPARATION-CLOSEOUT.md); packet49 device parity and speed pending. |
