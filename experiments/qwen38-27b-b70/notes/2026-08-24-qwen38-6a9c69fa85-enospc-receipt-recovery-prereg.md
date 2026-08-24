# 6a9c absolute-current build ENOSPC receipt recovery

Date: 2026-08-24. State: **preregistered; recovery not run.**

## Exact failed boundary

The audited dynamic zero-overlay builder resolved literal-current vLLM
`6a9c69fa851389dcf1ee5d3a2363e27af665d26d` (tree
`baf2301fb3f993537b07b6132b4d980efca2e7e4`, package
`0.26.1rc1.dev1157+g6a9c69fa8.xpu`), unchanged XPU kernels
`baaa05bb4e92901219a5a072dd63f2474896f6d1`, and unchanged nightly digest
`sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`.
It built the wheel and both immutable images with GPUs hidden. Both image
inspections and both static import/package/DSO preflights completed.

The both-current export and unpack completed, then the normal builder stopped
at line 497 while writing the both-current tag receipt:

```text
printf: write error: No space left on device
```

The root filesystem had zero available blocks. The both-current tag receipt
exists at zero bytes; the aggregate build receipt and intended USB archive do
not exist. Therefore the attempt is incomplete and unqualified even though the
images exist. No hardware gate, model, canary, benchmark, quality request,
cache compile, or GPU work ran.

Exact image identities are:

- current-vLLM/stock-kernel:
  `sha256:24ca5f6b6e5a14f71f43f82469f6e9debd36b2965942932e1646f377e30799cf`;
- both-current zero-overlay:
  `sha256:f86c4c78d76a484f5d54eda310419c91a2471634ab97782022ef7573fc19a7d9`.

The complete pre-recovery boundary is recorded in
[`2026-08-24-qwen38-6a9c69fa85-enospc-build-attempt.json`](../data/2026-08-24-qwen38-6a9c69fa85-enospc-build-attempt.json).

## Storage response

No source, image, model, run, patch, overlay, or result evidence was removed.
After the build process exited, only disposable caches were cleared: the host
uv cache, the host compiler cache, and Docker builder cache. All eight Docker
images, including both 342b and both 6a9c pairs, were retained and the new IDs
were reverified after builder-cache pruning. Root free space recovered to
`17,894,384 KiB`, above the unchanged `12,582,912 KiB` recovery/GPU floor.

## One-shot report-only recovery

Run
[`recover-20260824-qwen38-6a9c69fa85-enospc-build-receipt.sh`](../scripts/recover-20260824-qwen38-6a9c69fa85-enospc-build-receipt.sh)
once, only from clean pushed `main`. Its preregistered SHA-256 is
`e3f7da15e7ef90894b2629fd9e84eb25fc0eee00d68be1c8ffc44d1602610ba8`.

The recovery may not rebuild, retag, remove, or expose a GPU. It must fail
closed unless all of these remain exact:

- live vLLM, kernel, nightly, and clean pushed lab `main`;
- source head/tree, source archive, wheel/version, original build script and
  Dockerfile;
- official kernel artifact, workflow, and full configuration hashes;
- both stored inspections, IDs, tags, and complete image-label contracts;
- both stored static preflights and fresh no-network/no-device reruns;
- both in-image source identities;
- all three original build logs and the zero-byte failure boundary;
- the complete protected performance ledger, every TP1/TP2/TP4 floor embedded
  in source identity, and all 78 TP2 plus 152 TP4 preserved decision files.

Only after those checks may it preserve a structured failure snapshot, fill
the missing tag receipt, reconstruct an aggregate receipt with an explicit
`receipt_recovery` disclosure, and create a checksum-verified inert archive on
the NTFS USB volume. It must recheck all moving heads, lab state, and build
inputs after archival. There is no retry or partial-resume mode.

## Frozen interpretation

A recovery pass proves only that the already-built immutable images and their
static evidence are internally consistent. It creates no performance or
quality result and does not promote either image. A freshness movement closes
6a9c as dated evidence. If recovery passes while 6a9c remains literal-current,
track the recovered receipt, audit it independently, and only then derive a
fresh-root TP1 packet with every historical speed and quality gate unchanged.

TP2 and TP4 remain unauthorized until that current TP1 packet passes fully.
The 78 TP2 decisions and 152 accepted TP4 decisions remain separately
checksum-preserved and unapplied. MTP/source work stays separate until the
target-only TP4 lane closes.
