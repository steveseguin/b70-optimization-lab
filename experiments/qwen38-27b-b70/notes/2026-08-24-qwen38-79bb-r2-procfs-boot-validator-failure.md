# 79bb r2: hardware passed; procfs boot validator false-failed pre-model

Date: 2026-08-24. Status: **r2 closed failed-incomplete before any candidate
container, model, cache, canary, quality check, or timed benchmark ran. The
corrected four-card hardware gate passed completely.**

## Outcome

R2 proved the previous mixed-runtime diagnosis and correction. The fresh
hardware gate used the coherent virtualenv loader and passed all four card
identities, compute on each card, the four-device peer oracle, and one
four-rank XCCL barrier/all-reduce. The postflight was clean: kernel taint stayed
zero, the journal had no entries after the cursor, Docker remained empty, and
there were no render holders or residual probe processes.

The gate root is:

```text
/home/steve/qwen38-current-main-runs/postreboot-hardware-gate-79bb-20260824-086de284-venvlib-r2
```

Its 64-entry manifest verifies and hashes to
`c9c0720d4809df30642195aac107cd85e328fe306ccb5f6d7e75fd2ea69e0cbc`.
The summary hashes to
`538103f46123b7f26d8aaf56637d4245a99c85945cfe75b427e238f5ada6f434`
and records `passed=true`, `gate_complete=true`, exit zero.

The atomic wrapper then froze its input snapshot under:

```text
/home/steve/qwen38-current-main-runs/tp1-untreated-79bb-20260824-r2
```

Its first `verify_inputs` call emitted `host rebooted between untreated arms`
and stopped before `run_strict_arm`. The only subdirectory is `inputs`; all
three arms are missing with null medians. The 21-entry campaign manifest and
18-entry input manifest both verify. Their digests are respectively
`68e65ab397ebc64bfb832638c68e5358860449e3c0bad6d30fd1b2f1f2d682f9`
and `25188d38a5ab0dca54ed322baa8103616ca494668ce334e6f951acbd8c652a43`.
The complete structured record is
[`2026-08-24-qwen38-79bb-r2-procfs-boot-validator-failure.json`](../data/2026-08-24-qwen38-79bb-r2-procfs-boot-validator-failure.json).

## Proven cause

The host did not reboot. Its boot ID before, during, and after the chain is
`086de284-0771-4269-9cb2-e064fe303e40`. The live procfs value and frozen file
are byte-identical and share SHA-256
`bb9b7f66adbe173a11811c73f051dd678101e9e74160421367d20f4ff6348d5b`.

The frozen wrapper used:

```bash
cmp -s /proc/sys/kernel/random/boot_id "$inputs/host-boot-id.txt"
```

On this kernel the procfs sysctl reports regular-file size zero while the
snapshot reports 37 bytes. GNU `cmp -s` uses that metadata to return 1 without
reading the equal pseudo-file contents. Ordinary streaming `cmp` returns zero.
`/proc/cmdline` currently reports its 139-byte size and its quiet comparison
passed, but it is the same fragile direct-pseudo-file pattern.

This cause is independently reproduced rather than read from the generic
sealed failure JSON: that JSON retained the exit, identity, and missing arms
but did not capture the failure stage or stderr. The tracked record therefore
binds the raw digests and states that evidence boundary explicitly.

## Disposition

R2 contains no model performance or quality evidence. It changes no protected
floor, high, packet, or website cell. Both r2 roots are closed,
checksum-sealed, and must not be overwritten.

The minimal correction removes quiet metadata comparison only for the two
direct procfs sources. Normal `cmp` must read their bytes, still returning
nonzero for a real mismatch or read error. The frozen snapshots, hardware
gate, strict runner, candidate image, model, three arms, environment, graph,
cache, prompt, quality, timing, and speed-floor contracts remain unchanged.
A fresh commit-bound hardware gate is required because the r2 locks were
released; the passed r2 gate cannot be resumed as an atomic chain.
