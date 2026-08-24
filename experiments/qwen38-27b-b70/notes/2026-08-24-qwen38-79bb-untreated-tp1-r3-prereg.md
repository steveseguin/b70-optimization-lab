# 79bb untreated TP1 qualification r3: procfs validator correction

Date: 2026-08-24. State: preregistered, not yet launched.

## Purpose and evidence boundary

This is one infrastructure-only retry of the unchanged 79bb untreated TP1
program. R1 never started the candidate because the host XCCL gate mixed
runtime generations. R2 corrected that defect and its fresh hardware gate
passed completely, but the wrapper false-failed its first frozen-input check
because GNU `cmp -s` treated a zero-size procfs boot-ID source as different
from its byte-identical 37-byte snapshot. The
[`r2 closeout`](2026-08-24-qwen38-79bb-r2-procfs-boot-validator-failure.md)
preserves the exact raw roots and digests.

R3 changes only two pre-model validation commands. The existing snapshots of
`/proc/sys/kernel/random/boot_id` and `/proc/cmdline` remain exact. Their
direct checks change from quiet metadata-sensitive comparison to ordinary
streaming comparison with output discarded:

```bash
cmp -- /proc/sys/kernel/random/boot_id "$inputs/host-boot-id.txt" >/dev/null
cmp -- /proc/cmdline "$inputs/host-cmdline.txt" >/dev/null
```

Normal `cmp` reads the pseudo-file contents. Equal content returns zero;
mismatch returns one; an open or read error returns two. Every nonzero outcome
still stops fail-closed. No other `cmp`, snapshot, input permission, manifest,
freshness, image, or host gate changes.

## Frozen identity and unchanged performance contract

- vLLM main: `79bb395eea64dbfef99a55f010d2854db71f8571`, tree
  `3dc459a78f843186bb8a510631f9f1d34448a243`.
- XPU-kernel main: `baaa05bb4e92901219a5a072dd63f2474896f6d1`, tree
  `e7e7d1063f232a383c98c1820cebb94c45b4906e`.
- Official nightly base:
  `sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`.
- Both-current zero-overlay image:
  `sha256:786681b8aa4150d30e12af93b3038a03daba110719bf650a5c9d7c8804e0bdf3`.
- Host kernel and boot: `7.0.0-30-generic`,
  `086de284-0771-4269-9cb2-e064fe303e40`.
- Build receipt SHA-256:
  `92e8fa48ad09ee025fd16a8f29440d622715df0c300fade3023317cd756d948d`.
- Strict runner SHA-256:
  `cec5f3d852c84255822a4a5ee14d6829cd5efa6719ff9e8c59a904090d11c2b0`.
- Corrected hardware runner SHA-256:
  `84b9f5025476f40cb3218dbe513718c6d37da1e4852d17031b403fa410e4c506`.
- R2 wrapper provenance SHA-256:
  `063b42c363fc79451e34940a18373854214069ac306f7579a18db716b414f153`.

The exact suite, quality baseline, immutable image, candidate arguments, three
serialized TP1/GPU0 arms, ports, graph configuration, cache lifecycle,
natural-EOS split, quality-battery placement, timing helper/order, and outcome
interpretation remain those frozen by r2. The strict runner must have no Git
diff. Diagnostic and strict floors remain `30.2178` and
`30.31067504052998 tok/s`. No overlay or historical decision packet may run.

## Atomic cap and fresh roots

R3 may launch once through the full wrapper on fresh, disjoint ext4 roots:

```text
/home/steve/qwen38-current-main-runs/postreboot-hardware-gate-79bb-20260824-086de284-venvlib-r3
/home/steve/qwen38-current-main-runs/tp1-untreated-79bb-20260824-r3
```

It must start on clean pushed `main` equal to live `origin/main`, acquire and
hold the Muse lock, host lock, and four GPU leases across a new passing
commit-bound hardware gate and all model arms. There is no resume and no
internal retry. Any infrastructure, content, identity, canary, quality,
cleanup, journal, manifest, or freshness failure stops and preserves r3.

Live vLLM main, XPU-kernel main, and the official nightly digest must be
resolved after this packet is committed and again by the wrapper before and
between arms. Any movement closes 79bb stale; rebuild the absolute-newest
identity instead of launching or relabeling it.

## Frozen outcome

A full untreated pass authorizes separately preregistered current-base TP2,
then TP4. A completed speed miss with every non-speed gate clean preserves the
measurements and stops without an overlay; only then may a versioned 79bb
compatibility packet be derived. Any other result is not performance evidence.

No r3 outcome lowers or replaces any protected diagnostic/strict result or
captured high. The overall product priority remains complete, simple
neural.download coverage; this TP1 anchor exists to make the subsequent
TP2/TP4 and context/MTP/KV/graph matrix cells current and trustworthy.
