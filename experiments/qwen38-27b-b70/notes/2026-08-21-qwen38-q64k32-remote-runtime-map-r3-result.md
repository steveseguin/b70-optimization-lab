# Qwen3.8 Q64K32 remote runtime-map r3 valid result

Date: 2026-08-21

Status: **valid positive; classification `valid-no-clock-runtime-map-match`;
the A0 diagnostic is complete**. The structured summary is
[`../data/2026-08-21-qwen38-q64k32-remote-runtime-map-r3-result.json`](../data/2026-08-21-qwen38-q64k32-remote-runtime-map-r3-result.json),
and the controlling registration is
[`2026-08-21-qwen38-q64k32-remote-runtime-map-diagnostic-prereg.md`](2026-08-21-qwen38-q64k32-remote-runtime-map-diagnostic-prereg.md).

## What ran

The reference host `steve-TURIND8-2L2T` was clean on `main == origin/main` at
`7a2363f03e6f816ba8ebd34d824c38f9a9357ca4` (the independently reviewed r3
source correction), on the same boot as the passive scan
(`a6cad22f-2685-43b7-8950-c0c771f73d99`). The frozen preflight passed and the
driver ran exactly once against the fresh root:

```text
/home/steve/qwen38-q64k32-remote-runtime-map-diagnostic-20260821-r3
```

All four fresh workers ran in the exact preregistered order (GPU0 control,
GPU0 candidate, GPU1 candidate, GPU1 control), each performing one eager
M6/head256/KV128 production-shape operator call under the hardened supervisor.
Every arm passed its terminal validation, and the final comparison published
`passed=true`. The root holds exactly 34 max-depth-one regular files, all mode
`0444`, with aggregate
`dcf563a9fed00be1aaf640f8249a4a26c9cacad52bb395f67e590c3e973caea1`
from the r2 note's basename-sorted `sha256sum` recipe. The raw files remain
remote-only and were not copied into Git.

## Findings

1. **Mapped runtime identity is established.** Every pre- and post-call map in
   all four arms equals the eight r2-observed portable
   raw/canonical basename/path/SHA rows (projection
   `ba940a22a21a030be60ae54a33cac4f31560e4745565b2dd51e91203a16bffd3`), the
   full rows including live device/inode agree before/after and across all
   four same-boot processes, and every before-to-after map delta is empty.
2. **The remote CPU oracle is same-host deterministic, and r2 is conclusively
   a cross-host pin false-fail.** All four arms computed the identical oracle
   digest
   `eb71753ec76de2390e25f5bebacecf54cb63f7966311cdd6548a5ed03638364a`, equal to
   r2's observation. Four fresh processes across two device bindings reproduce
   one oracle byte stream on this host; the r2 rejection is therefore fully
   explained by the nonportable measuring-host pin, not remote instability.
3. **Stock and Q64K32 outputs are byte-identical on this fixture.** All four
   arms, control and candidate on both devices, produced output digest
   `c3e022a5e724574d06e2388e33e2e29c4b1f8630f2b7eb236ffc5e349fe9c403`, equal to
   r2's XPU output and the prior local control output. This is consistency
   evidence on the frozen KV128 fixture only.

Per-arm artifact and terminal digests, plus the comparison and preflight-scan
digests, are recorded in the structured summary.

## Boundaries

This is a bounded no-clock runtime-map result. It makes no timing, throughput,
endpoint, acceptance, or clock claim, and it does not qualify or reject the
Q64K32 policy anywhere. It supplies the mapped Level Zero/SYCL runtime
basename/SHA evidence that clock-campaign prerequisite 5 requires, but the
16-arm campaign remains blocked until the A1 campaign-authority commit freezes
this worker-map evidence into the still-placeholder source gates, implements
the strict direct-child authorization-receipt contract, and closes the
remaining prerequisites (stage-identity binding, same-boot device recapture,
launch-time composite revalidation, clock-writer exclusion, and the final
reviewed gate replacement). `CAMPAIGN_LAUNCH_AUTHORIZED` and
`CLOCK_WRITER_EXCLUSION_AUTHORIZED` remain `False`.
