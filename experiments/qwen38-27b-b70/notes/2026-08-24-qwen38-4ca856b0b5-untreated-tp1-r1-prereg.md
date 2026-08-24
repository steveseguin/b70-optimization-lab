# 4ca856b0b5 untreated TP1 qualification r1

Date: 2026-08-24. State: **closed stale before launch; never launched.**

## Purpose and evidence boundary

This is the first atomic untreated TP1 qualification for literal-current vLLM
`4ca856b0b5` and exact-current XPU kernels. The prior 79bb R3 program passed its
hardware gate, fresh diagnostic, strict replay-A canary/benchmark/full quality
battery, cache immutability, and cleanup, then correctly stopped
`stale-before-promotion` when vLLM main advanced during replay A. Its sealed
[`closeout`](2026-08-24-qwen38-79bb-r3-stale-during-replay-a.md) is not a
completed qualification and authorizes no 79bb overlay or TP2/TP4 run.

The 4ca packet carries forward the proven R3 harness, including the ordinary
byte-reading procfs comparisons. There is no functional benchmark change.
The 79bb R3 wrapper provenance SHA-256 is
`0ac97192ee7482e001c439a9b969ce86b212841b8d45c7a5593f240b844568ac`.

## Frozen identity

- vLLM main: `4ca856b0b59d87c7b167d1bd8c748421719c9a57`, tree
  `442cbede8a32127f18899cb1f2442031b3a8adbd`;
- XPU-kernel main: `baaa05bb4e92901219a5a072dd63f2474896f6d1`, tree
  `e7e7d1063f232a383c98c1820cebb94c45b4906e`;
- official nightly base:
  `sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`;
- current-vLLM/stock-kernel image:
  `sha256:f872e8fc477df5b63ef8ef07a1c90a676b8f238dfa3999a48ec855b5c994775b`;
- both-current zero-overlay image:
  `sha256:11806bd940bf5870e897ab6bd700da8d16f97b4d96fabb16aabb93b607ce8070`;
- build receipt SHA-256:
  `d416f9f26642739f371a45226427b40094295318fd29af9f8780d815b66699f7`;
- strict runner SHA-256:
  `cec5f3d852c84255822a4a5ee14d6829cd5efa6719ff9e8c59a904090d11c2b0`;
- hardware runner SHA-256:
  `84b9f5025476f40cb3218dbe513718c6d37da1e4852d17031b403fa410e4c506`;
- host kernel and boot: `7.0.0-30-generic`,
  `086de284-0771-4269-9cb2-e064fe303e40`.

The only vLLM source delta since 79bb is security documentation plus the
multiprocess-executor worker-RPC payload lifetime change and its tests. No
Qwen, XPU, graph/speculative, dependency, native-build, or Rust file changed.
That lowers TP1 risk but does not waive qualification; the executor delta is
potentially relevant at TP2/TP4.

## Frozen benchmark and performance contract

The suite (`292dea6a...`), quality baseline (`738b8ed0...`), model manifest,
model verifier, realistic benchmark helper, quality helper, strict runner,
hardware runner, accelerator-clean environment, graph configuration, cache
lifecycle, request order, timing path, natural-EOS split, and quality placement
remain exact.

The serialized GPU0 arms remain:

1. fresh-cache diagnostic on port 19761, MTP0/F16/32K/graph, floor
   `30.2178 tok/s`;
2. same-cache strict natural-EOS quality replay A on port 19762, floor
   `30.31067504052998 tok/s`;
3. same-cache strict natural-EOS replay B on port 19763, the same strict floor.

No source, decision, DSO, binary, generated-kernel, or cache overlay may run.
The TP2 78-decision and TP4 152-decision artifacts remain separately versioned
and unapplied. This untreated packet cannot silently discard them: it only
establishes the new zero-overlay base to which compatible decisions may later
be remapped and freshly compiled.

## Atomic cap and fresh roots

R1 may launch once through the full wrapper on fresh, disjoint ext4 roots:

```text
/home/steve/qwen38-current-main-runs/postreboot-hardware-gate-4ca856b0b5-20260824-086de284-venvlib-r1
/home/steve/qwen38-current-main-runs/tp1-untreated-4ca856b0b5-20260824-r1
```

It must start from clean pushed `main` equal to live `origin/main`, with at
least the unchanged 12-GiB root headroom, and hold the Muse lock, host lock,
and four GPU leases across a fresh commit-bound hardware gate and every model
arm. There is no resume, internal retry, or root overwrite. Any infrastructure,
identity, content, canary, benchmark, quality, cache, cleanup, journal,
manifest, or freshness failure stops and seals R1.

Live vLLM main, XPU-kernel main, and the official nightly digest must be
resolved after this packet is committed, immediately before the hardware gate,
and before/after each arm. Any movement closes 4ca stale and requires building
the successor instead of launching, continuing, or relabeling it.

## Frozen outcome

A complete untreated pass authorizes a separately preregistered current-base
TP2 packet, then TP4. A completed speed miss with every non-speed gate clean is
preserved and stops without an overlay; only that terminal classification may
authorize deriving a separately versioned 4ca compatibility packet. Any other
result is incomplete evidence.

No outcome lowers, replaces, or hides any protected floor/high or accepted
decision result. The purpose of TP1/TP2/TP4 anchoring is the larger product
goal: a clean neural.download interface backed by explicit measured,
estimated, screened, closed, unsupported, or missing states across family,
quantization, topology, MTP depth, context, KV, graph, runtime, and overlay
axes.

## Closure

An independent prelaunch audit at `2026-08-24T14:49:17Z` resolved live vLLM
main to `ecfa7bb37316a3c1dab345fea4178d81f63b1ce4`, not the frozen 4ca head.
XPU-kernel main and the official nightly digest remained unchanged. R1 was not
invoked: neither fresh root was created, all three ports remained unbound, no
container or model started, and no hardware or GPU work ran.

This is a clean stale-before-qualification closure, not infrastructure,
correctness, quality, or speed evidence. Its benchmark contract remains the
frozen provenance for a separately named successor packet after that successor
is built from the literal newest head. The TP2 78-file and accepted TP4
152-file decision overlays remain verified, versioned, and unapplied; no
accepted performance work was discarded.

This closure edit intentionally invalidates the stale wrapper's frozen
preregistration SHA pin. Keep that mismatch as an additional nonlaunch guard;
do not repin or run the obsolete 4ca wrapper. Derive a separately named wrapper
and preregistration only after the successor build identity is sealed.
