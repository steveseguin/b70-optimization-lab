# Ornith 1.5 35B shared-gate/residual/RMS work-group sweep

Status: **performance negative; do not promote**.

## Question

The accepted twelve-feature stack fuses the scalar shared-expert gate,
sigmoid, broadcast multiply, routed/shared addition, residual addition, RMS
normalization, and final norm-weight multiply. Because this is a Qwen-derived
Ornith graph, we tested whether the smaller work-group geometry used by some
earlier Qwen kernels transfers to this new fused kernel.

The candidate added a default-off
`GGML_SYCL_ORNITH_MOE_GATE_RESIDUAL_RMS_WG` override for 256, 512, or 1024
threads. An unset variable retained the device maximum (1024 on this B70).

## Correctness gate

Default, 512, and 256 used the same candidate binary and produced the same
659-byte canonical transcript:

`2e7965fcdc273f0433df359cff5188ae3585426fd32f28536121d1b5e35dad18`

The fused feature fired 35,880 times in every seven-repetition benchmark arm.

## Matched ladder

One B70, target-only, depth 0, 128 generated tokens, F16 KV, seven repetitions
per arm, sequence `default / 512 / 256 / default`:

| Arm | Mean decode | Std. dev. | Delta vs bracketed default mean |
| --- | ---: | ---: | ---: |
| default A1 | 135.912325 tok/s | 1.678809 | — |
| WG512 | 133.332816 tok/s | 2.219084 | -1.6159% |
| WG256 | 131.792016 tok/s | 1.887482 | -2.7528% |
| default A2 | 135.133053 tok/s | 1.920212 | — |

The bracketed default mean is 135.522689 tok/s. Both smaller geometries lose
clearly, so no server screen is warranted. The accepted device-max geometry
remains unchanged.

## Artifacts and restoration

- Raw benchmark rows are `data/ornith-gate-resid-wg-*.json`.
- Dispatch counters are `data/ornith-gate-resid-wg-*.stderr.log`.
- The rejected incremental source is preserved in
  `patches/llamacpp-ornith15-shared-gate-residual-rms-workgroup-negative-20260823.patch`.
- After the screen, the source diff returned to the accepted twelve-feature
  SHA-256 `7b9204f8f44608fc5b1858a15498b3cf9bf52b4f02c27c0f91a1807af5b5d15d`.
  CLI, server, and bench hashes also returned exactly. The rebuilt AOT SYCL
  shared object was not byte-reproducible across links, so its binary hash is
  deliberately not used as a restoration claim.
