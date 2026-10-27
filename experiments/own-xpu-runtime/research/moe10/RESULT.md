# MoE combine scheduling experiment

`OWNRT_MOE10=1` was an F32 vector-load schedule for the ten-expert combine. It handled four adjacent outputs per work
item, preserved every output's e=0..9 product/add sequence, and used a volatile product to prevent contraction.

`test_moe10_compare.cpp` compared incumbent and candidate on the same OpenCL CPU device: all outputs and sentinels were
byte-identical. Guard tests had no inactive/sticky-error writes and correctly rejected negative/capacity positions.

The full rank-1 GPU gate compared 1,079 target buffers with zero differences and identical tokens, but the 4096-row
prompt was slower:

| B24 reference | Vector candidate |
|---:|---:|
| 15.490 s | **16.750 s** |

The variant is rejected and was not integrated. An earlier ten-lane gather was also rejected during CPU qualification;
no GPU result is claimed for it. This closes the experiment rather than motivating another schedule sweep.
