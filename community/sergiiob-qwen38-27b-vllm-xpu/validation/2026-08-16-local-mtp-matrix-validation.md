# Local native-MTP matrix validation — 2026-08-16

## Outcome

The exact captured SergioB vLLM/XPU configuration reproduces on one ASRock
Arc Pro B70 at 8K context. The local MTP4 median is **83.7019248652 tok/s**,
effectively identical to the contributor's provisional **83.7 tok/s** row.

All four local modes used the same five unique p512/g128 prompts, FP8 KV,
prefix cache disabled, EOS ignored, one same-shape warmup, normal host power
policy, and the exact target model/image. Both captured patches were active for
MTP1/2/4. The container was limited to 8 GiB RAM and 10 GiB RAM+swap.

A subsequent MTP4 run omitted both patches and reached **83.6971534912
tok/s**, only `-0.005700%` versus patched. It reproduced the exact 510/544
acceptance pattern and all five output hashes. For this pinned model at 8K,
the nightly build patch is redundant and the boundary patch is not exercised.

## Local matrix

| Mode | Median decode | Mean | Min–max | Accepted / proposed | Acceptance | Contributor claim |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| target-only graph | 33.690260 | 33.691220 | 33.686637–33.698090 | n/a | n/a | 32.9 |
| MTP1 | **54.175761** | 54.143366 | 53.999088–54.200424 | 320 / 320 | 100.000% | 52.0 |
| MTP2 | **68.232180** | 68.124136 | 67.047836–68.609173 | 423 / 436 | 97.018% | 65.8 |
| MTP4 | **83.701925** | 84.238634 | 81.174501–87.570452 | 510 / 544 | 93.750% | 83.7 |

Relative to the local target-only graph control, MTP1/2/4 improve the median
by 60.805%, 102.528%, and 148.445%. Cache hit and cache query deltas were zero
throughout. The runtime counters demonstrate that these are native MTP draft
tokens accepted by the target verifier, not DFlash or response reuse.

## Output parity and quality boundary

Every MTP1, MTP2, and MTP4 visible output is byte-identical to the matching
target-only graph and eager output for all five prompts. The five shared output
hashes are recorded in the target-only validation note.

This is a strong narrow correctness gate for greedy decoding, but not a full
semantic or benchmark-quality evaluation. All modes use FP8 KV, whose accuracy
class remains distinct from FP16 KV. The contributor's exact prompts and raw
run tree are not public, so this is an independent compatible reproduction,
not a byte-identical replay of their campaign.

## Patch A/B and dtype boundary

The logs prove that the captured nightly patch executed and selected its
unquantized-draft branch:

```text
[B70] MTP draft: forcing unquantized build (env B70_MTP_BF16_DRAFT=1)
```

The patch-off MTP4 A/B matched patched performance, acceptance, device memory
(17.38 GiB model load), and output hashes. This dynamically confirms the source
review: the pinned model's built-in `-:.*mtp.*` dynamic exclusion already keeps
the draft outside target GPTQ. Prefer `PATCH_MODE=off` at 8K. Retain the nightly
patch only as provenance/compatibility material for older checkpoints whose
config lacks the exclusion.

The boundary patch addresses an incomplete final speculative group at the
exact 131,072-token boundary. This 8K run neither needs nor validates it.

The artifact's 15 `mtp.*` tensors are BF16 on disk, but the engine's global
runtime dtype is `torch.float16`. This test does not establish the loaded draft
parameter dtype; continue to label runtime draft precision unknown until it is
directly inspected.

## Resource behavior

- MTP1 model load: 17.38 GiB device memory; graph capture: 3.63 GiB.
- MTP2 startup approached the 8 GiB host-memory boundary but completed without
  OOM, restart, GPU fault, reset, or hang.
- MTP4 also completed under the same cgroup without a device or kernel fault.
- Each server was stopped before starting the next mode.
- No power cap or clock control was changed.

## Evidence hashes

Raw evidence remains under
`/mnt/fast-ai/bench-results/qwen38-gptq-int4-asrock-b70-20260816/`.

```text
eb96e7ffe265b931ceb0ccec5b1884086e64b3a7be099f18b66d4a4810dd77bb  mtp1-graph-u088-p512-g128-n5/results.json
e7a97780e026d3701ec9172e91170df46bb76bea8d99af395dd4fecb14e7a38e  mtp2-graph-u088-p512-g128-n5/results.json
54972d00fc87075c3f49b6b56a45dceb3a1d6f66868b410eeb7cc96c04136b02  mtp4-graph-u088-p512-g128-n5/results.json
91aeeca2e48e0b5d0f0bc1b442b70f6b623760110b9e92da35a96cd948e52f8a  mtp1-graph-u088-server.log
cead717f8876a1cc90de80c58d128e49482aecd9373660fb0bac5212a4b790c3  mtp1-graph-u088-container-inspect.json
09966fe31602dc1d9e3644e34f4ef20487720b574719dd7420b76eeabe77648b  mtp2-graph-u088-server.log
94a2ff782c7ca6af90d40c81a8534915758f063ef7c933e8d588322de0eea3bb  mtp2-graph-u088-container-inspect.json
5e45c67b3bc8bd0eccbffa5f18e074834f1a5cfc8a884a8750b7ad92c7a17073  mtp4-graph-u088-server.log
f9f5824cbef5ea08af49647c1f38a93bc69de34cc78b4784d37508b1ae07438f  mtp4-graph-u088-container-inspect.json
88c8000b7f74fdf35bd0042b9891332a17993347d7a50975b6efb517e09ce1bd  mtp4-unpatched-graph-u088-p512-g128-n5/results.json
1cb0fe801bccc6ac299d86f363d401be16128fad4e92c05eb596b1c8fb5782c9  mtp4-unpatched-graph-u088-server.log
1141ee8ba57df29dc9eaa881b95c44264e6325cfd9564ce5450819e81cf66284  mtp4-unpatched-graph-u088-container-inspect.json
```

The shared prompt and target-only evidence hashes are in
[`2026-08-16-local-target-only-graph-validation.md`](2026-08-16-local-target-only-graph-validation.md).
