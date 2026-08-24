# 342b8ebd8b both-current zero-overlay TP1 qualification r2

Date: 2026-08-24. State: **preregistered; not launched.**

## Purpose and prior-attempt boundary

R1 is sealed failed-incomplete after completing the diagnostic and strict
replay A. Its diagnostic passed at `30.337988469031558 tok/s`; replay A passed
the full quality battery at `30.295550825778708 tok/s` but missed the frozen
strict floor by `0.015124214751271 tok/s`. Before replay B, an unrelated lab
repository commit advanced live `origin/main`, so the wrapper stopped and no
aggregate result exists. R1 cannot resume, and none of its cache or generated
outputs may enter r2. See the
[r1 closeout](2026-08-24-qwen38-342b8ebd8b-r1-repo-advanced-after-replay-a.md).

R2 is a fresh-root repetition of the complete untreated TP1 sequence because
342b remains literal-current and r1 was interrupted by repository coordination,
not by an engine-upstream, model, quality, cache, kernel, or cleanup failure.
The observed r1 speed miss remains real evidence; r2 does not erase it or
weaken its floor. R2 must independently pass diagnostic, strict A, strict B,
quality, cache, and freshness gates to qualify.

The r2 wrapper is a mechanical copy of the audited r1 wrapper. Its only
behavior-neutral substitutions are this preregistration identity, fresh
non-overridable `r2` roots, and ports `19773`-`19775`. The classifier, fourteen
tests, corrected-NVMe-aware hardware gate, strict runner, model and quality
inputs, graph/cache lifecycle, environment, and performance floors remain
byte-identical.

## Frozen runtime identity

- vLLM main: `342b8ebd8bd4595826f29ff95dfc48679a03a95a`, tree
  `7b60b566f69b2d158016082486b0ed4f3c430715`, package
  `0.26.1rc1.dev1156+g342b8ebd8.xpu`;
- XPU-kernel main: `baaa05bb4e92901219a5a072dd63f2474896f6d1`, tree
  `e7e7d1063f232a383c98c1820cebb94c45b4906e`;
- official nightly base:
  `sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`;
- stock-kernel image, retained but not run by this packet:
  `sha256:23fe2e1c88e2c0f5c69b00370687a07c2c49aa1f4fea903ff9416b0223690c37`;
- both-current zero-overlay image:
  `sha256:6dbd46c8d22c3fdb425dfe343e759a89c5aa443eb99f411b4f6d923eae2e54ae`;
- build receipt SHA-256:
  `ad856716714af8893d0ce47416d0efab4e9cb014505e6deeed3b3545ea82141c`;
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

An independent resolution at `2026-08-24T18:42:22Z` matched all three moving
engine identities. Root free space was `13,977,792 KiB`, above the unchanged
`12,582,912 KiB` launch floor. These point-in-time checks do not waive the
wrapper's immediate pre-gate and per-arm checks.

## Frozen benchmark and performance contract

The wrapper runs, in order:

1. fresh-cache diagnostic, TP1/MTP0/F16/32K/XPU Graph, port `19773`, floor
   `30.2178 tok/s`;
2. same-cache strict natural-EOS quality replay A, port `19774`, floor
   `30.31067504052998 tok/s`;
3. same-cache strict natural-EOS replay B, port `19775`, the same floor.

Every arm uses the both-current zero-overlay image, GPU 0, one request,
`FULL_AND_PIECEWISE` capture sizes `[1,2]`, `PYTHONHASHSEED=0`, cache-zero
requests, and the fixed 25-prompt realistic suite. Strict speed is the
conventional median over the 99 inter-token intervals between generated events
1 and 100. Replay A retains all seven objective exact cases, eight-run repeat,
8K needle, 24 baseline comparisons, and immutable-cache gate. Both strict arms
must independently meet the unchanged historical floor.

The cache begins absent on ext4, is created only by the diagnostic arm, and
must be byte-identical before and after both strict replays. R1's 1,097-file
cache is preservation evidence only and is forbidden as an input.

No source patch, Triton decision, DSO, generated binary, historical compiled
cache, or prior run artifact is applied. The TP2 78-decision packet and accepted
TP4 152-decision overlay remain separately checksum-preserved, disabled, and
unapplied. The unqualified TP1 38-decision candidate also remains disabled.

## Kernel, model, and repository gates

The exact r1 kernel-event contract remains frozen. Every bounded raw journal
delta is retained, the canonical reject pattern remains broad, and at most one
exact 21-line corrected Samsung root-NVMe block may be classified separately.
Any mutation, fragment, second block, GPU/Xe event, warning, reset, timeout,
filesystem error, or other reject line fails closed. The fourteen-test battery
must pass before hardware work.

The hardware gate retains four-device identity and compute, peer read,
four-rank XCCL all-reduce, coherent runtime, root-NVMe health, clean journal,
taint, repo postflight, selector/mask exclusion, lock handoff, and cleanup
checks. Each model arm must directly and ordinarily verify all 19 model files,
load the exact image/source receipt, return exact canary `14` with zero cached
tokens, and leave no container, listener, or render-node holder.

R2 must start from clean pushed `main` equal to live `origin/main`. All other
agents must remain read-only and no unrelated commit or push may occur during
the atomic hardware/diagnostic/A/B window. The wrapper still verifies local
status, branch, frozen commit, local tracking ref, and live remote ref between
arms; any repository movement stops and seals r2. This coordination rule does
not relax a byte or identity check.

## Atomic cap and fresh roots

R2 may launch once through the full wrapper on these exact non-overridable
fresh roots:

```text
/home/steve/qwen38-current-main-runs/postreboot-hardware-gate-342b8ebd8b-20260824-086de284-venvlib-r2
/home/steve/qwen38-current-main-runs/tp1-untreated-342b8ebd8b-20260824-r2
```

It must hold the Muse lock, host lock, and all four GPU leases across the
commit-bound hardware gate and every arm. There is no resume, overwrite,
partial-arm launch, or internal retry. Any infrastructure, source, model,
canary, benchmark, quality, cache, cleanup, journal, manifest, speed,
repository, or freshness failure stops and seals r2.

## Frozen interpretations and next gate

- A complete r2 pass qualifies this exact 342b both-current zero-overlay TP1
  profile and authorizes a separately preregistered current TP2 zero-overlay
  packet.
- A completed speed miss with every non-speed gate clean is the only outcome
  that can authorize a separately versioned TP1 decision-compatibility packet;
  it does not lower a protected result.
- An upstream move closes 342b as dated and requires a newest-head rebuild.
- A repository-only movement yields incomplete evidence and no topology
  authorization.
- Any other result is incomplete or rejected evidence under its exact cause.

After TP1 passes, proceed to TP2 zero-overlay, then remap and retest only the 78
path/config-hash-compatible decisions in a separate fresh cache. TP4 follows
with its zero-overlay control and separately remapped accepted 152-decision
packet. Do not copy this TP1 runner's `PYTHONHASHSEED=0` or memory settings into
those historically unset-hash multi-GPU identities. Current MTP source-port
work stays separate until the target-only TP4 lane closes.
