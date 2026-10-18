# Packet74: packed dense weights

CPU preparation only. Four sealed views share one engine binary. All sources
were copied from frozen packet70; prior packets and shared screens were not
edited. The coordinator owns all device runs. No speed result is claimed.

| View | Changed resident target tensors | Draft |
| --- | --- | --- |
| production | none; packet70 wide64 experts / draft-HC / batch rollback | unchanged |
| head-packed | rank1 Q6_K output head only | original expanded91,392-row prefix kept separately |
| dense-packed | selected Q6_K/Q8_0 dense projections on both ranks | unchanged shared expanded head |
| combined | both changes | original expanded prefix kept separately |

Selected projections are QKV, Z, Q-gate, QSA K/V, attention output, PLE key/value
and shared down. Fused HC and small-FFN tuples keep their expanded storage and
kernels. Raw F32/BF16 matrices and packed routed experts are unchanged. This is
an explicitly scoped dense candidate, not a replacement for every dense site.

`p74_packed.hpp` reads original GGUF bytes: aligned wide loads of ql/qh with
register shifts, original half×signed-subscale multiplication, then scale×code.
It handles the alternating two-byte alignment of210/34-byte blocks without
out-of-bounds reads. Q8's final eight-code group uses aligned halfword edges.
There is no full-weight decode buffer, SLM staging or decoder launch. The
original eight-elements/lane traversal, adjacent SG32 tree and split4 merge
remain. Builds disable fast math/FMA and retain IEEE denormals.

`main.cpp` chooses storage at initialization and uploads packed blocks instead
of expanded copies. Normal projections use one kernel; attention retains its
original partial-sum plus stream-combine pair. Packet49 and
`iq3-p49-split32-v1` remain the full-model authority. KV is unchanged.

GNU and Intel each pass two fresh CPU fixture processes:60 cases and5,657,600
dequant comparisons each, exact FP32 lane sums, BF16 outputs and attention
tails. Both engine builds and the standalone device microbenchmark compile.
Device output parity, deterministic repeats and speed remain pending.

- [History and milestones](../../../../notes/2026-10-17-own-runtime-packet74.md)
- [VRAM accounting](VRAM.md), including the retained draft prefix
- [Coordinator commands and selection rule](WINDOW.md)
- [Microbenchmark contract](MICROBENCH.md)
- [CPU evidence](evidence/cpu-byte-identity.json), [build](build-device-receipt.json)
- [Preparation closeout](CPU-PREPARATION-CLOSEOUT.md), [boundaries](DO-NOT-REPEAT.md)
