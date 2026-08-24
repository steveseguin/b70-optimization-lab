# 6a9c69fa85 both-current zero-overlay TP1 qualification r1

Date: 2026-08-24. State: **preregistered; not launched.**

## Purpose and prior-attempt boundary

This is the first qualification attempt for the literal-current vLLM
`6a9c69fa85` build. No prior 6a9 diagnostic, strict replay, cache, or result
exists, and no root, cache, generated output, or run artifact from an earlier
vLLM identity may enter r1.

The build completed both image exports, inspections, and static preflights.
ENOSPC interrupted the normal writer before the aggregate receipt and archive;
the preregistered report-only recovery revalidated the immutable image IDs,
source and wheel hashes, labels, preflights, repository state, and all three
moving upstream identities before sealing the receipt and archive. It did not
rebuild, retag, remove, patch, expose a GPU, or change any performance input.
See the
[recovery record](2026-08-24-qwen38-6a9c69fa85-enospc-recovery-pass.md).

The r1 wrapper is a mechanical successor to the audited 342b r2 wrapper. Its
only behavior-neutral substitutions are the 6a9 source, receipt, image and
preregistration identities, fresh non-overridable `r1` roots, ports
`19783`-`19785`, and 6a9/r1 evidence labels. The classifier, fourteen tests,
corrected-NVMe-aware hardware gate, strict runner, model and quality inputs,
graph/cache lifecycle, environment, and performance floors remain
byte-equivalent.

## Frozen runtime identity

- vLLM main: `6a9c69fa851389dcf1ee5d3a2363e27af665d26d`, tree
  `baf2301fb3f993537b07b6132b4d980efca2e7e4`, package
  `0.26.1rc1.dev1157+g6a9c69fa8.xpu`;
- XPU-kernel main: `baaa05bb4e92901219a5a072dd63f2474896f6d1`, tree
  `e7e7d1063f232a383c98c1820cebb94c45b4906e`;
- official nightly base:
  `sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`;
- stock-kernel image, retained but not run by this packet:
  `sha256:24ca5f6b6e5a14f71f43f82469f6e9debd36b2965942932e1646f377e30799cf`;
- both-current zero-overlay image:
  `sha256:f86c4c78d76a484f5d54eda310419c91a2471634ab97782022ef7573fc19a7d9`;
- build receipt SHA-256:
  `a7b2d9a4fa1693c4ca83e98a494b249a380087963702c0f30cf558bb889400f3`;
- kernel-delta classifier SHA-256:
  `fef74bdb90b82fdf543be6ea36320b308aff0d0c146a3c92bcbfff334b70d1b0`;
- classifier test SHA-256:
  `b21befd70003b710027303e093915c36ce88d8fcd4eda66facfd549057e5474b`;
- strict runner SHA-256:
  `5647c9af599fb4a3bc31b8cf8118c986f8895842de9cd657c037e4ea099925da`;
- hardware runner SHA-256:
  `8038015b179048662f53d7d41ead6cddc95671081942444f394c6e48ed57a6f7`;
- host kernel and boot: `7.0.0-30-generic`,
  `086de284-0771-4269-9cb2-e064fe303e40`.

The receipt recovery resolved all three moving engine identities at
`2026-08-24T19:30:48Z`, and the post-recovery audit resolved the same heads and
digest again. Recovery recorded `17,883,424 KiB` root free space, above the
unchanged `12,582,912 KiB` launch floor. These point-in-time checks do not
waive the wrapper's immediate pre-gate and per-arm checks.

## Frozen benchmark and performance contract

The wrapper runs, in order:

1. fresh-cache diagnostic, TP1/MTP0/F16/32K/XPU Graph, port `19783`, floor
   `30.2178 tok/s`;
2. same-cache strict natural-EOS quality replay A, port `19784`, floor
   `30.31067504052998 tok/s`;
3. same-cache strict natural-EOS replay B, port `19785`, the same floor.

Every arm uses the both-current zero-overlay image, GPU 0, one request,
`FULL_AND_PIECEWISE` capture sizes `[1,2]`, `PYTHONHASHSEED=0`, cache-zero
requests, and the fixed 25-prompt realistic suite. Strict speed is the
conventional median over the 99 inter-token intervals between generated events
1 and 100. Replay A retains all seven objective exact cases, eight-run repeat,
8K needle, 24 baseline comparisons, and immutable-cache gate. Both strict arms
must independently meet the unchanged historical floor.

The cache begins absent on ext4, is created only by the diagnostic arm, and
must be byte-identical before and after both strict replays. All caches from
older vLLM identities are preservation evidence only and are forbidden as
inputs.

No source patch, Triton decision, DSO, generated binary, historical compiled
cache, or prior run artifact is applied. The TP2 78-decision packet and accepted
TP4 152-decision overlay remain separately checksum-preserved, disabled, and
unapplied. The unqualified TP1 38-decision candidate also remains disabled.

## Kernel, model, and repository gates

The exact audited kernel-event contract remains frozen. Every bounded raw
journal delta is retained, the canonical reject pattern remains broad, and at
most one exact 21-line corrected Samsung root-NVMe block may be classified
separately. Any mutation, fragment, second block, GPU/Xe event, warning, reset,
timeout, filesystem error, or other reject line fails closed. The fourteen-test
battery must pass before hardware work.

The hardware gate retains four-device identity and compute, peer read,
four-rank XCCL all-reduce, coherent runtime, root-NVMe health, clean journal,
taint, repo postflight, selector/mask exclusion, lock handoff, and cleanup
checks. Each model arm must directly and ordinarily verify all 19 model files,
load the exact image/source receipt, return exact canary `14` with zero cached
tokens, and leave no container, listener, or render-node holder.

R1 must start from clean pushed `main` equal to live `origin/main`. All other
agents must remain read-only and no unrelated commit or push may occur during
the atomic hardware/diagnostic/A/B window. The wrapper verifies local status,
branch, frozen commit, local tracking ref, and live remote ref between arms;
any repository movement stops and seals r1. This coordination rule does not
relax a byte or identity check.

## Atomic cap and fresh roots

R1 may launch once through the full wrapper on these exact non-overridable
fresh roots:

```text
/home/steve/qwen38-current-main-runs/postreboot-hardware-gate-6a9c69fa85-20260824-086de284-venvlib-r1
/home/steve/qwen38-current-main-runs/tp1-untreated-6a9c69fa85-20260824-r1
```

It must hold the Muse lock, host lock, and all four GPU leases across the
commit-bound hardware gate and every arm. There is no resume, overwrite,
partial-arm launch, or internal retry. Any infrastructure, source, model,
canary, benchmark, quality, cache, cleanup, journal, manifest, speed,
repository, or freshness failure stops and seals r1.

## Frozen interpretations and next gate

- A complete r1 pass qualifies this exact 6a9 both-current zero-overlay TP1
  profile and authorizes a separately preregistered current TP2 zero-overlay
  packet.
- A completed speed miss with every non-speed gate clean is the only outcome
  that can authorize a separately versioned TP1 decision-compatibility packet;
  it does not lower a protected result.
- An upstream move closes 6a9 as dated and requires a newest-head rebuild.
- A repository-only movement yields incomplete evidence and no topology
  authorization.
- Any other result is incomplete or rejected evidence under its exact cause.

After TP1 passes, proceed to TP2 zero-overlay, then remap and retest only the 78
path/config-hash-compatible decisions in a separate fresh cache. TP4 follows
with its zero-overlay control and separately remapped accepted 152-decision
packet. Do not copy this TP1 runner's `PYTHONHASHSEED=0` or memory settings into
those historically unset-hash multi-GPU identities. Current MTP source-port
work stays separate until the target-only TP4 lane closes.
