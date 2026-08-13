# Qwen3.6 27B Q8 TP2 target-only state-I/O record

Date: 2026-08-13

Hardware: 2x ASRock Intel Arc Pro B70 32 GiB

Objective: improve Q8_0 TP2 decode without MTP, DFlash, or other speculation

## Outcome

The final packaged-recipe cold suite measured **35.494434 tok/s** under conventional
99-inter-token-interval accounting. The repository's historical helper reports
`35.852963 tok/s` from the same timestamps. All 12 prompts produced 512 tokens,
all cache counts were zero, and all 12 complete output hashes matched the
accepted pre-state-I/O target-only control.

This is `+14.405%` over the matched mndodd-fork TP2 baseline of `31.025377
tok/s` conventional. It clears the requested 30 tok/s two-card target without
using speculative decoding or changing the Q8_0 target.

The authoritative artifacts are:

- [result packet](../results/qwen36-27b-q8-tp2-asrock-b70/README.md)
- [standalone repro](../repro/qwen36-27b-q8-tp2-asrock-b70/README.md)
- [complete source patch](../patches/qwen36-27b-q8-tp2-asrock-b70/README.md)
- [structured summary](../data/qwen36-q8-tp2-asrock-b70-20260813/summary.json)
- [mndodd contributor baseline](../community/mndodd-qwen36-27b-llamacpp-sycl/README.md)

## Final progression

| Stage | Conventional median | Change |
| --- | ---: | ---: |
| Matched mndodd fork | `31.025377` | — |
| Lab fusion stack before direct state I/O | `33.967039` | `+9.481%` vs mndodd |
| Direct recurrent GDN state I/O | `35.030949` | `+3.132%` incremental |
| Direct recurrent convolution state I/O, matched run | `35.330307` | `+0.855%` incremental |
| Packaged-recipe confirmation | **`35.494434`** | `+0.465%` run variance |

The source-change attribution uses the matched `35.330307` run and therefore
stays conservative. The higher end-to-end recipe replay is the promoted score;
its extra `0.465%` is treated as ordinary run variance, not another code gain.

The GDN transformation recognizes only the exact one-sequence recurrent
`GET_ROWS -> GDN -> CPY` state path. It reads and updates the persistent state
in place. The convolution transformation recognizes only the exact one-token,
`d_conv=4`, 5,120-channel `GET_ROWS -> CONCAT/CPY -> SSM_CONV` path. Its fused
kernel loads the three persistent values and current input, follows the stock
runtime accumulation loop, emits the convolution result, and shifts the state
in place. Both matchers fail closed on alternate shapes, strides, types,
consumer counts, or pointer relationships.

The final server reported `588672` accepted executions for each direct state-I/O
path over the long suite. A convolution poison build changed the first prompt's
clean output hash and produced corrupt text, confirming that the green suite
actually traversed the new kernel. Both poison variables are explicitly unset
by the repro and production launchers.

## Quality decision

An earlier convolution prototype spelled the four multiply-adds explicitly.
It was fast but changed 1 of 12 complete output hashes and was rejected. Using
the stock runtime loop form restored 12/12 byte identity while retaining a
measurable long-suite gain. No approximate reduction, altered KV precision,
draft acceptance, or hidden cache was admitted.

## Rejected doors

- GDN workgroup packing at 2, 4, 8, and 16 subgroups was flat; the knob was
  removed and the original four-subgroup geometry retained.
- A strict batched Q/K normalization plus in-kernel RoPE path matched all 12
  short outputs but was performance-neutral and was removed.
- VDR2/VDR8, scale broadcast, alternate GDN reuse, convolution-to-SiLU, Q8
  cache, asynchronous tensor copy, root-barrier elision, forced PVC-style
  phase ordering, and root-local peer replication were previously rejected.
- TP2 graph capture aborted or hung. The built-in TP2 profiler reset both
  compute engines. Neither belongs in a production or benchmark recipe.

## Host safety and deployment

The host has about 15 GiB RAM. BMG AOT builds ran separately from model loads
under a 6 GiB soft / 8 GiB hard memory cgroup. Model runs used an 8 GiB soft /
10 GiB hard memory cap plus at most 8 GiB swap. This avoids repeating the
unbounded build-plus-model pressure that previously froze the machine.

The promoted target-only endpoint is `qwen36-q8-b70.service` on loopback port
18080. After deployment it passed `/health`, an exact 128-token cache-zero
smoke, and GPU/kernel post-stress checks. Both cards remained `normal`; no Xe
fault, reset, hang, AER error, or OOM event was found.

## Next bounded step

The next Qwen 27B release should first be probed in a fresh modern-upstream
llama.cpp checkout for architecture conversion, target-only load, and a fixed
quality oracle. Only then should exact-shape pieces of this patch be transferred;
the recurrent graph and state geometry must not be assumed unchanged.
