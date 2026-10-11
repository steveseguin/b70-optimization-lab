# Packet 12 rejected assumptions

| Assumption | Evidence | Revisit condition |
| --- | --- | --- |
| 60 layers describes this checkpoint | Census and packet3 say 36 GDN + 12 QSA | A different authenticated model |
| One end-of-layer 10 KiB exchange supplies both attention and MoE dependencies | Packet3's HC/attention/router dependency chain | A proven equivalent graph, including all casts |
| Two deterministic expert partials equal the original ten-slot sum | CPU cancellation counterexample; slot-order contract | Exact reconstruction of the original order, not a replaced oracle |
| Contiguous K halves retain packet2's tree32 arithmetic | lane_dot strides 32 before adjacent-pair tree | Tree-preserving split plus lossless layout proof |
| Same-card D2D 270–540 GB/s is PCIe peer speed | Packet5 measured local D2D only | Actual bidirectional peer receipts |
| Peer ACCESS permits spin polling or remote atomics | MiniMax IPC 417 ms and failed visibility tests | Different proven mechanism and quality evidence; this packet uses events |
| Each card necessarily processes five experts | Top-10 can all fall in one ID half | Measured routing distribution/placement evidence |

[Preparation closeout](CLOSEOUT.md); no device arm has been run in this packet.
