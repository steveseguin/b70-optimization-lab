# Qwen3.8 27B Q8 TP2 register-direct collective tail workgroup

Date: 2026-08-17

Status: closed; WG768 regressed `0.357%`, WG512 regressed `3.102%`, and
WG256 regressed `5.019%` against WG1024 in position-balanced screens.

## Hypothesis

At each of the 128 TP boundaries per generated token, the accepted path runs a
5,120-element register-direct residual/RMS/multiply/Q8 tail on each B70. The
tail currently uses the device maximum of 1,024 work-items: each thread visits
five RMS elements and 64 SG16 subgroups share 160 Q8 blocks. A smaller
workgroup may reduce scheduling and reduction overhead while retaining enough
parallel Q8 block ownership.

This is distinct from the closed `GGML_SYCL_COMM_REDUCE_WG` experiment, which
changed only the preceding elementwise cross-device root reduction and left
both RMS/Q8 tails unchanged. It is also distinct from the neutral five-element
loop-unroll experiment, which retained the 1,024-work-item geometry.

## Contract

- isolated same-binary runtime selector, defaulting to the accepted 1,024;
- admit only 256, 512, 768, or 1,024 work-items for the exact 5,120-element
  register-direct path;
- retain tensor split, model, F16 KV, target-only execution and every promoted
  fusion;
- mechanism smoke with `VERIFY_MISMATCH=0` and post-run GPU health;
- position-balanced performance screen before endpoint work;
- because workgroup size changes the RMS reduction tree, any fixed-prompt or
  complete-suite output-hash difference is a hard rejection regardless of
  speed;
- retain 1,024 unless a candidate is repeatably faster and clears the full
  cache-zero output oracle plus semantic/long-context gates.

## Mechanism smoke

`GGML_SYCL_COMM_DIRECT_Q8_WG=256` announced on the exact register-direct path
in a TP2 `p64/n1` smoke. The accepted fusion census remained live,
`VERIFY_MISMATCH=0`, and decode completed at `35.859675 tok/s`. Both B70s
remained normal with no current-boot Xe/GuC fault, reset, timeout or hang.

## Mirrored performance result

Fresh-process order was `1024, 256, 512, 512, 256, 1024`, each at
`p64/n256/r3`, equal TP2, F16 KV, FlashAttention and `b1024/ub256`.

| Tail workgroup | Run means (tok/s) | Pooled sample mean | Delta vs WG1024 |
| ---: | --- | ---: | ---: |
| 1,024 | `37.079787`, `37.263951` | `37.171867` | -- |
| 512 | `35.999896`, `36.037986` | `36.018933` | **`-3.1016%`** |
| 256 | `35.311990`, `35.300333` | `35.306167` | **`-5.0191%`** |

Both candidate widths repeated closely and were materially slower than both
controls. No fixed-prompt or endpoint quality suite was warranted because
neither passed the performance gate. Keep the accepted 1,024-work-item tail;
do not repeat 256 or 512 unchanged.

## WG768 completion

The initially unmeasured valid intermediate width was added to the same-binary
selector and built with oneAPI 2026.1.1. A `p0/n1` smoke announced WG768 and
reported `verified=1980`, `VERIFY_MISMATCH=0`.

A fresh `p64/n512/r3` A-B-B-A screen compared WG1024 and WG768 from that same
library:

| Position | Workgroup | Decode, tok/s |
| ---: | ---: | ---: |
| 1 | 1024 | `37.593491` |
| 2 | 768 | `37.459263` |
| 3 | 768 | `37.465671` |
| 4 | 1024 | `37.600171` |

WG1024 averaged `37.596831 tok/s`; WG768 averaged `37.462467 tok/s`, a
`-0.357381%` regression. Both treatment positions lost and repeated closely,
so WG768 did not earn an endpoint quality gate. This completes the practical
multiple-of-256 sweep: retain WG1024 and do not retry WG256, WG512, or WG768
unchanged.

## Reproduction artifacts

- structured result:
  [`../data/2026-08-17-q8-collective-tail-workgroup-negative.json`](../data/2026-08-17-q8-collective-tail-workgroup-negative.json)
- incremental patch after the accepted Q8 stack:
  [`../patches/q8-collective-tail-workgroup-negative-20260817.diff`](../patches/q8-collective-tail-workgroup-negative-20260817.diff)
- incremental patch SHA-256 (including the WG768 completion):
  `a1ab6158a6e8502c4aa75e298763ba2dba5c77ee58fc1c98aea103c02204ea94`
- isolated source/build: `/mnt/fast-ai/src/llama.cpp-q38-q8-fixed-shapes`,
  `build-sycl-aot-bmg-g31-fixed-shapes` (the unrelated fixed-shape door was
  unset for every arm)
- `libggml-sycl.so.0.19.0` SHA-256:
  `95e0c3569667b5036dddddc3a2a8339192774c9740721caa14a4150ca393dc33`
- `llama-bench` SHA-256:
  `5ad7c26b123d41194a72f127052c50414a58a558a120548f17f11d54dba61abb`
- raw local evidence:
  `/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260817-tail-wg/`
- WG768 extension `libggml-sycl.so.0` SHA-256:
  `17c2c18fa2deb9cd5bd0727dff7d075670c69a136fbb19dc95fd3274cdabe916`
- WG768 extension raw evidence:
  `/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260817-tail-wg768/`
