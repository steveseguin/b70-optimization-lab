# 7797b6022c untreated TP1 qualification r1

Date: 2026-08-24. State: **preregistered; not launched.**

## Purpose and evidence boundary

This is the first atomic untreated TP1 qualification for literal-current vLLM
`7797b6022c` and exact-current XPU kernels. The intervening ecfa and f620 builds
were never launched and are preserved as dated build evidence. This packet
carries forward the proven R3 harness, including ordinary byte-reading procfs
comparisons, with no functional benchmark change and no source, decision, DSO,
binary, generated-kernel, or cache overlay.

The latest upstream commit adds per-architecture tuned configurations to the
generic batch-invariant persistent matmul path, but its tuned selection requires
BF16 plus `VLLM_BATCH_INVARIANT` on CUDA Ada/Hopper. This anchor is F16, does
not enable that global mode, and XPU resolves the exact prior default
configuration because `current_platform.is_cuda()` is false. The upstream
"~3x" title is therefore not a B70 gain and must not be reported as one. The
source identity still changed, so static review does not waive the diagnostic,
strict replay, cache, quality, or performance gates. A speed-only miss is
evidence for a separately preregistered compatibility packet; it never
authorizes changing a floor or silently applying historical decisions in this
invocation.

## Frozen identity

- vLLM main: `7797b6022c129b862e45ae6aed08822e65d1bccb`, tree
  `78e0ffe9e07831fa2af9643e0c87501000a93014`;
- XPU-kernel main: `baaa05bb4e92901219a5a072dd63f2474896f6d1`, tree
  `e7e7d1063f232a383c98c1820cebb94c45b4906e`;
- official nightly base:
  `sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`;
- current-vLLM/stock-kernel image:
  `sha256:a385f20ca68b62f18d670722617ed69583fe9154b537c108f04b704029950abd`;
- both-current zero-overlay image:
  `sha256:295de005ad89735c92aced11179d05db08dd694badff3722de3f1ceb9e5994f1`;
- build receipt SHA-256:
  `be82b2b6b5b94600d9b736dd9d8f11f48e9b475c13efa74adcda0829d510abba`;
- strict runner SHA-256:
  `cec5f3d852c84255822a4a5ee14d6829cd5efa6719ff9e8c59a904090d11c2b0`;
- hardware runner SHA-256:
  `84b9f5025476f40cb3218dbe513718c6d37da1e4852d17031b403fa410e4c506`;
- host kernel and boot: `7.0.0-30-generic`,
  `086de284-0771-4269-9cb2-e064fe303e40`.

The normal builder completed both images, the full static preflight, aggregate
receipt, external archive copy, archive checksums, and a post-archive live
freshness seal. At `2026-08-24T15:36:20Z`, canonical vLLM main, XPU-kernel
main, and the official nightly digest still matched the frozen identity.

## Frozen benchmark and performance contract

The suite (`292dea6a...`), quality baseline (`738b8ed0...`), model manifest,
model verifier, realistic benchmark helper, quality helper, strict runner,
hardware runner, accelerator-clean environment, graph configuration, cache
lifecycle, request order, timing path, natural-EOS split, and quality placement
remain exact.

Two new prelaunch assertions are identity-only: the archived wheel must contain
`batch_invariant_configs.py`, and the measured image must not set
`VLLM_BATCH_INVARIANT`. They neither add a launch variable nor change the model,
cache, request, quality, or timing path.

The serialized GPU0 arms are:

1. fresh-cache diagnostic on port 19761, MTP0/F16/32K/graph, floor
   `30.2178 tok/s`;
2. same-cache strict natural-EOS quality replay A on port 19762, floor
   `30.31067504052998 tok/s`;
3. same-cache strict natural-EOS replay B on port 19763, the same strict floor.

No source, decision, DSO, binary, generated-kernel, or cache overlay may run.
The TP2 78-decision and TP4 152-decision artifacts remain separately versioned
and unapplied. This untreated packet does not discard them: it establishes the
new zero-overlay base to which only exact-path/config-hash-compatible decisions
may later be remapped and freshly compiled. Generated kernels and outer caches
must never be copied.

## Atomic cap and fresh roots

R1 may launch once through the full wrapper on fresh, disjoint ext4 roots:

```text
/home/steve/qwen38-current-main-runs/postreboot-hardware-gate-7797b6022c-20260824-086de284-venvlib-r1
/home/steve/qwen38-current-main-runs/tp1-untreated-7797b6022c-20260824-r1
```

It must start from clean pushed `main` equal to live `origin/main`, with at
least the unchanged 12-GiB root headroom, and hold the Muse lock, host lock,
and four GPU leases across a fresh commit-bound hardware gate and every model
arm. There is no resume, internal retry, or root overwrite. Any infrastructure,
identity, content, canary, benchmark, quality, cache, cleanup, journal,
manifest, or freshness failure stops and seals R1.

Live vLLM main, XPU-kernel main, and the official nightly digest must be
resolved after this packet is committed, immediately before the hardware gate,
and before/after each arm. Any movement closes 7797 stale and requires building
the successor instead of launching, continuing, or relabeling it.

## Frozen interpretations and next gate

- A complete untreated pass authorizes a separately preregistered current-base
  TP2 packet, then TP4.
- A completed speed miss with every non-speed gate clean is preserved and stops
  without an overlay; only that terminal classification may authorize deriving
  a separately versioned compatibility packet.
- Any other result is incomplete evidence.

No outcome lowers, replaces, or hides any protected floor/high or accepted
decision result. After the target-only TP1/TP2/TP4 anchors, run the separately
bounded native-MTP boot/canary sentinel motivated by the generic attention
metadata change in f620. Broader family/quant/MTP/context/KV/graph coverage then
follows the canonical neural.download coverage plan; this current-base anchor
is a prerequisite, not the product endpoint.
