# Packet74 exact allocation deltas

These are allocation calculations from pinned tensor headers, not measured GPU memory. The inherited memory admission remains conservative. Draft keeps its expanded91,392-row prefix, original kernel, and original outputs. It does not keep a second expanded full head.

| View | Rank0 fewer bytes | Rank1 fewer bytes | Extra draft prefix bytes |
| --- | ---: | ---: | ---: |
| production | 0 | 0 | 0 |
| head-packed | 0 | 8,944,640 | 308,904,960 |
| dense-packed | 661,749,760 | 673,382,400 | 0 |
| combined | 661,749,760 | 682,327,040 | 308,904,960 |

Q6 head:839,321,600 expanded resident bytes become521,472,000 packed bytes plus308,904,960 draft-prefix bytes: net8,944,640 saved. Target traffic falls794,624,000→521,472,000 bytes (34.375%). QKV Q6:34,611,200 resident→21,504,000; useful reads32,768,000→21,504,000. Q8 saves10.526% resident and5.556% fetched bytes. All block and row bytes are exact; no padding or full-size decode scratch is allocated.

The dense view retains fused HC and small-FFN tuples and their expanded bytes. Its router is raw F32, so no router weight format is silently changed. Routed experts and official BF16/INT8 draft tensors are unchanged. PLE key/value are included on rank0.

[Per-tensor identity and totals](VRAM.json). Actual peak and speed remain unmeasured.
