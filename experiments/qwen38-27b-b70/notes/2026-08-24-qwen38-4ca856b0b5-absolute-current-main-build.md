# Qwen3.8 absolute-current 4ca build

Date: 2026-08-24. Status: **both zero-overlay images built and statically
certified; closed stale before qualification; never launched.**

## Exact identity

- vLLM `main`: `4ca856b0b59d87c7b167d1bd8c748421719c9a57`, tree
  `442cbede8a32127f18899cb1f2442031b3a8adbd`, package
  `0.26.1rc1.dev1146+g4ca856b0b.xpu`;
- XPU-kernel `main`: `baaa05bb4e92901219a5a072dd63f2474896f6d1`,
  tree `e7e7d1063f232a383c98c1820cebb94c45b4906e`, official wheel
  `7b886fa814469aef8904118729f31f2fe77559f3c5219bd0ecf799a904387483`;
- official nightly runtime base:
  `sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`;
- current-vLLM/stock-kernel image:
  `sha256:f872e8fc477df5b63ef8ef07a1c90a676b8f238dfa3999a48ec855b5c994775b`;
- both-current zero-overlay image:
  `sha256:11806bd940bf5870e897ab6bd700da8d16f97b4d96fabb16aabb93b607ce8070`.

The tracked byte-identical
[`build receipt`](../data/2026-08-24-qwen38-4ca856b0b5-absolute-current-main-build.json)
hashes to
`d416f9f26642739f371a45226427b40094295318fd29af9f8780d815b66699f7`.
The external archive is:

```text
/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/current-main-builds/20260824T143242Z-4ca856b0b5-baaa05bb4e
```

Its 14-entry `SHA256SUMS` verifies and hashes to
`576ec37583778fc48d10f7c06b81609aafd5790c632fa1586573e52bb2a186e0`.
The source identity and built vLLM wheel hash respectively to
`a30744be816944a599621ab72b9333ff2af48bfccd384a240a8a41bdc0c652af`
and `402c5ac6dac2f9a14f758d08b01c8d04a8b13856cb3c67c57708d5bdaea61097`.

Both images passed package/import, exact source/label, Rust artifact, required
XPU DSO, linkage, and narrowly scoped dependency checks. No GPU was exposed.
The build source, wheel, image labels, Dockerfile, and receipt contain no
source, decision, DSO, binary, or cache overlay.

## Upstream delta and performance boundary

Relative to the closed 79bb build, `9f295fe8` added only security
documentation. `4ca856b0` then changed the multiprocess executor so each worker
RPC payload is released before the next dequeue, plus tests. It did not change
Qwen, XPU kernels, graph/speculative code, dependencies, native build inputs,
or Rust. It may still affect TP2/TP4 worker memory lifetime or host overhead,
so no topology is assumed equivalent and every result remains GPU-pending.

The accepted TP2 78-decision artifact, accepted TP4 152-decision performance
overlay, protected launch/runtime contract, and all historical floors/highs
remain separate and append-only. Zero-overlay TP1 qualifies first. Compatible
decisions may later be remapped by relative path plus embedded config hash into
a fresh compile; generated kernels and old outer caches never transfer.

## Storage disposition

The build temporarily reduced root headroom below the unchanged 12-GiB launch
gate. Pruning only unused Docker build cache recovered 7.652 GB. The measured
79bb both-current image was then streamed by exact ID to:

```text
/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/current-main-builds/20260824T124051Z-79bb395eea-baaa05bb4e/both-current-image-786681b8aa41.docker.tar.zst
```

The archive hashes to
`46a27b5ab8c5c728ecb3bfb41ca7a998410066c2d69db7225a6bdb632ee9078c`;
zstd integrity and all 38 Docker-tar entries pass, with 5,682,309,842
compressed and 5,713,477,632 uncompressed bytes. Only after those checks was
the stale local image ID `786681b8aa41...0bdf3` removed. The new 4ca images,
all run evidence, sources, wheels, overlays, and protected results remain
local or durably archived. Root headroom became 14,153,704 KiB.

## Next action

The independent prelaunch audit at `2026-08-24T14:49:17Z` resolved vLLM main
to `ecfa7bb37316a3c1dab345fea4178d81f63b1ce4`; XPU-kernel main and the
official nightly digest remained unchanged. No hardware gate, container,
model load, cache, benchmark, quality request, or GPU arm launched. The frozen
R1 wrapper would have stopped at its first freshness check, so the packet was
closed without running it.

The direct one-commit delta from 4ca caches common token sequences in the
multimodal processor and fourteen multimodal/model files. It does not touch
this dense text-only Qwen, INC/AutoRound, XPU, graph, GDN, collective,
dependency, Rust, or kernel path. That lowers expected port risk but does not
waive the literal-newest build and full qualification.

This 4ca build is dated, unlaunched evidence. Preserve its exact receipt,
archive, local image IDs, and zero-overlay binding. Build ecfa or whatever is
newest at the next resolution, retain the exact 79bb R3 benchmark and safety
contract, and never relabel this packet or lower a protected result.
