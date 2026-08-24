# 79bb qualification stopped at a mixed-runtime host XCCL gate

Date: 2026-08-24. Status: **closed as failed-incomplete infrastructure;
no candidate image, model, cache, canary, or timed benchmark ran.**

## Outcome

The first atomic 79bb qualification attempt stopped in its fresh hardware
gate. All four exact B70 identities passed, each card completed the standalone
Torch compute oracle, and the four-device peer-read kernel passed. All four
XCCL ranks then returned from `init_process_group` and printed `init ok`, but
all four received `SIGSEGV` at the first `dist.barrier`. The parent exited 1
and never created
`/home/steve/qwen38-current-main-runs/tp1-untreated-79bb-20260824`.

The closed, checksum-sealed raw root is:

```text
/home/steve/qwen38-current-main-runs/postreboot-hardware-gate-79bb-20260824-086de284
```

All 54 entries in its `SHA256SUMS` verify. The manifest digest is
`5a47a865cf1e66c44ed5153625fdb553db1258fdc912532f9b831d234b6b823a`.
The structured receipt is
[`2026-08-24-qwen38-79bb-hardware-gate-mixed-runtime-failure.json`](../data/2026-08-24-qwen38-79bb-hardware-gate-mixed-runtime-failure.json).

This is not performance evidence. It neither lowers nor replaces the protected
TP1/TP2/TP4 diagnostic or strict floors, and it says nothing about 79bb decode
speed or correctness because image
`sha256:786681b8aa4150d30e12af93b3038a03daba110719bf650a5c9d7c8804e0bdf3`
never started.

## Cause and evidence boundary

The failed collective used the old host virtualenv, not either built 79bb
image: Torch `2.11.0+xpu`, oneCCL `2021.17.2`, and vLLM
`0.20.2rc1.dev2+gc51df4300.d20260523.xpu`. The gate forced the system oneAPI
2026 library path. Static loader resolution therefore combined the
virtualenv's `libsycl.so.8` and oneCCL with the different system-2026
`libur_loader.so.0`.

This matches the already retained
[`2026-05-06` incident](../../../notes/2026-05-06-fp8-venvlib-pp2-tp4.md):
all ranks initialized and then segfaulted at `dist.barrier` when system oneAPI
libraries preceded the matching virtualenv runtime; virtualenv-first ordering
recovered XCCL. In this attempt every rank faulted in `__strlen_avx2` at the
same invalid address class, consistent with a deterministic native-runtime
metadata failure. The corrected run is still required before calling the
cause proven on this boot.

There is no evidence for an xe hang, GuC reset, AER fault, device loss, kernel
taint, or persistent render-node holder. The passing per-card and peer tests
also argue against treating this as a sick-card result. No reboot, reset,
module operation, or shared-memory deletion is warranted from this evidence.

Two independent gate defects were found at the same time:

- the reject regex omitted generic `segfault`, so the old summary's
  `kernel_reject_events: 0` means only zero matches to its incomplete pattern;
- the success oracle used whole-line rank markers even though torchrun
  concatenates rank writes. The exact false-abort and accepted substring-count
  correction are already documented in the
  [July log-framing incident](../../laguna-s-2.1-xpu-b70/notes/2026-07-23-w1-n128-nvme-xccl-log-framing-preflight-abort.md).

## Disposition

The old root is closed and must not be overwritten or reinterpreted. The safe
continuation is one separately preregistered atomic attempt on new roots. Its
host Torch subprocess must use only the matching virtualenv runtime, pin the
effective Torch/SYCL/oneCCL/UR files and their loader origins, count every
fixed rank marker exactly once regardless of physical-line framing, and treat
any segfault as a journal reject. A second failure stops without looping.

Nothing in that correction may change the immutable candidate image, strict
runner, model, prompt suite, graph configuration, cache protocol, metric, or
speed floors. If the corrected gate passes, the same untreated TP1 diagnostic
and strict A/B arms remain next, followed by separately preregistered TP2 and
TP4 on the same literal-current source identity.
