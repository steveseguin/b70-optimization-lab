# Laguna exact M=8 shared-elementwise fusion component result

Date: 2026-07-23 America/Toronto

## Result

The preregistered four-card component gate passed in full. The separate-input
shared SiLU/multiply operation and the routed-scale/shared-add operation were
bitwise exact before and after timing on every physical B70. Each individual
operation and the combined treatment won all `31/31` paired A-B-B-A blocks on
all four cards.

The combined treatment reduced the measured device launches for one
47-layer target cycle from `188` to `94`, exactly the preregistered
94-launch reduction. Its paired median saving was `0.699138-0.722866 ms` per
cycle across the four cards, clearing the `0.15 ms` floor by more than 4.6x
even on the slowest result.

This authorizes a separately preregistered cold endpoint experiment. It is not
itself endpoint-throughput evidence and is not eligible for a LocalMaxxing
submission.

## Frozen identity

- vLLM:
  `8936aac144929190c1e53f8b8624ca397ce16f5b`;
- XPU kernels:
  `b6076ce1249ffee0e30bee528f4cd15c3bffb234`;
- component-gate freeze:
  `54df510da9455beb710c5dcebf33d248b23cc7d9`;
- gate script SHA256:
  `c6ab407fd62bea38f9fda4f8d51c32cd9ed6f0e323f01eef322e0f57a76911fd`;
- rebuilt `_C.abi3.so` SHA256:
  `126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2`;
- CMake compiler:
  `/opt/intel/oneapi/compiler/2025.3/bin/icpx`, Intel oneAPI DPC++/C++
  `2025.3.3` (`2025.3.3.20260319`);
- build-log SHA256:
  `b6be73134749cbd8e86a231979bca6c4e68e221b2d411314bd7524547a0a5d09`;
- Torch: `2.12.0+xpu`;
- XPU driver: `1.15.38308+1`; and
- common 31-fixture timing-bank SHA256:
  `7041f8432c66552c78a3ff5e8a85511600b3f1727bab2b020156a5da387ec76a`.

The build log is:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/shared-elementwise-build-b6076ce-20260723T061703Z/build.log
```

It records a successful focused `_C` build from the committed kernel source.
The first PATH-level `icpx --version` diagnostic reports the separately
installed 2026.0 compiler, but the CMake cache and explicit cached compiler
diagnostic identify the compiler that actually built `_C` as 2025.3.3. The
log also corrects an initially unconditional binary-comparison message:
CMake install intentionally rewrote RUNPATH to `$ORIGIN`, and the installed
binary hash above is the frozen runtime identity.
All four formal runs independently validated clean source trees, the expected
source commits, loaded native-library path and hash, physical-card identity,
driver tooling, record environment, and the two native symbols.

## Exactness and dispatch evidence

On each card, shared activation correctness covered:

- all 65,280 finite BF16 gate bit patterns with `up=1`;
- all finite gate patterns paired with reversed finite up values;
- all finite gate patterns paired with signed-zero/subnormal values;
- the known exponential midpoint at gate bits `0x40be`, whose PyTorch BF16
  SiLU result is `0x40bd`;
- 256 changing random `[8,256]` epochs; and
- a full post-timing replay of the exhaustive corpus.

Scale-plus-add correctness covered all 65,280 finite BF16 routed patterns
against zero, one, signed-zero, and reversed-finite shared inputs, plus 256
changing random `[8,3072]` epochs and the full post-timing exhaustive replay.
All comparisons used raw BF16 equality against the literal incumbent
two-operation arithmetic.

Every card also passed the vLLM fail-closed contract checks. Only matching
eager Laguna target-verifier M=8 calls dispatched the native operations.
M=1, verifier tails M=2..7, prefill, and draft calls retained the incumbent
path. Compiled calls and missing native symbols raised. The matching dispatch
counts were exactly one activation and one scale-add native call in the
focused probe on every card, with common output hashes:

```text
activation  8a4cd3b5da60ecedaa1ecb0c1df7faf6c7c37c32f7c0ba9ed6759fd28f047403
scale_add   4d5f55e2e79aaed27fd8c40cecce19438c693dc80a6b48058246d04ea556039d
```

The XPU profiler counted 47 `laguna_m8_silu_mul` launches and 47
`laguna_m8_scale_add` launches for the candidate. The literal control issued
47 launches for each of SiLU, activation multiply, routed scale, and shared
add: 188 total.

## Frozen timing result

Each timing family used 20 warm cycles per arm, 31 A-B-B-A blocks, 64 complete
47-layer cycles per timed arm, inference mode, synchronization only at arm
boundaries, and one prebuilt changing fixture per block.

| Card | Operation | A control ms/cycle | B candidate ms/cycle | Paired saving ms | B wins |
| ---: | --- | ---: | ---: | ---: | ---: |
| 0 | activation | 0.525711 | 0.217344 | 0.307935 | 31/31 |
| 0 | scale+add | 0.516464 | 0.229523 | 0.286666 | 31/31 |
| 0 | combined | 1.152387 | 0.451744 | 0.700692 | 31/31 |
| 1 | activation | 0.525301 | 0.214297 | 0.311095 | 31/31 |
| 1 | scale+add | 0.510594 | 0.224732 | 0.286244 | 31/31 |
| 1 | combined | 1.152020 | 0.446353 | 0.705373 | 31/31 |
| 2 | activation | 0.528979 | 0.219595 | 0.309246 | 31/31 |
| 2 | scale+add | 0.525052 | 0.231800 | 0.293177 | 31/31 |
| 2 | combined | 1.157378 | 0.458973 | 0.699138 | 31/31 |
| 3 | activation | 0.538743 | 0.223012 | 0.315701 | 31/31 |
| 3 | scale+add | 0.527633 | 0.233715 | 0.293804 | 31/31 |
| 3 | combined | 1.187274 | 0.463970 | 0.722866 | 31/31 |

Every individual result exceeds its 24/31-win and positive-saving gates.
Every combined result exceeds its 28/31-win and `>=0.15 ms` gates. No
cross-card average was used to hide a weak card.

## Invalid identity-tool preflight preserved

The earlier directory:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/shared-elementwise-component-gate-8936aac-b6076ce-be84cf6-20260723T062024Z
```

is not valid four-card evidence. Card 0 completed under script SHA
`d909e16352b8f8160126286e7808c4ab82700c9e369aa3c8335d6322debf5450`,
but card 1 stopped in identity validation before its correctness or timing
candidate ran:

```text
identity gate failed: expected physical card is absent from xpu-smi discovery
```

The old identity helper interpreted affinity-filtered `xpu-smi` discovery as
physical numbering. With card 1 exposed as the only Level Zero device,
`xpu-smi` presented it as visible device 0, so the helper incorrectly declared
physical card 1 absent. This was a tooling preflight failure, not a kernel,
quality, or performance result. No service or model was started and no
endpoint generation occurred. The partial card-0 output was not reused.

The corrected gate records both unfiltered physical discovery and filtered
visible-device discovery, binds the requested physical card to its PCI
identity, and has script SHA
`c6ab407fd62bea38f9fda4f8d51c32cd9ed6f0e323f01eef322e0f57a76911fd`.
All four cards were then rerun from scratch into the newly named valid root:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/shared-elementwise-component-gate-8936aac-b6076ce-54df510-20260723T062317Z
```

Raw valid JSON SHA256s for cards 0 through 3 are, respectively:

```text
3ed3f48e2b759dcda0cb57fe9c5acfebcaee1ca28f6f1f228587ed89bc22bba6
681c871590aa3385da79b27a3c9e08b0d6b7081da66d325d9f5951597fd23128
cb6d2af72429e8632fb0149db09617d7c371970b8d4e4ed351ba20b330f1d9f6
160746051da99d41cfcab1ec7698fcb449e9b2be89b4fcd77323522020920389
```

The compact tracked summary is:

```text
data/laguna-s-2.1-shared-elementwise-component-20260723.json
```

## Disposition

Keep `VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE` default-off outside a frozen
record experiment. The component result authorizes the separately
preregistered shared-elementwise plus QKNorm/RoPE cold endpoint stack. It does
not authorize changing either projection GEMM, any collective, any reduction,
or the BF16 router path.
