# Qwen3.8 AutoRound lane-transition handoff audit

Date: 2026-08-18

Scope: remote transition commit `26728e40e` as merged by `262479730`, reviewed
read-only on the two-B70 host after a fast-forward pull.

## Verified

- The four original files in
  `patches/qwen36-27b-autoround-int4-b70/determinism-closeout-20260818/`
  matched their original `SHA256SUMS` before the editorial corrections recorded
  in the subsequent audit commit.
- `vllm-determinism-commits.bundle` passes `git bundle verify` when verified
  from a vLLM repository containing prerequisite
  `95a76ff89173ff56e90a2ed384fde2cea3c015e6`.
- The bundle contains final head
  `44fc8fde09fc311d3099dab10366b672d9142ea4` and the two advertised sampler
  commits.
- Applying `vllm-sampler-final-working.patch` to the exact prerequisite and
  indexing the result produces tree
  `cf7a49e1cedd40b08d4254f4f7b56abdfc87c36a`, exactly matching the recorded
  final head. The flat patch is therefore a complete source reconstruction for
  those two commits.
- The independently downloaded Qwen3.8 model matches pinned revision
  `bce40cacab0a4535b92fb3d57615c2bea9adf3d1` and the tracked model manifest.
- Local source trees match vLLM `44fc8fde09` and XPU kernels `2dd55f380d` and
  are clean. Both Intel Arc Pro B70 devices are discovered by the read-only
  preflight.

## Qualified claims

The Qwen3.8 and Qwen3.6 AutoRound checkpoints have matching tensor architecture
and quantization layout. That establishes mechanical source compatibility; it
does not establish that the whole transferred stack is already quality-,
determinism-, or performance-equivalent for the new weights.

The first Qwen3.8 summary reports `91.925538 tok/s` over all 25 prompts and
`86.719870 tok/s` over the historical selection-12 subset. It remains an
unpromoted measuring-host observation because the compact raw rows, matching B
replicate, and Qwen3.8 target-only quality oracle are not in this checkout.

## Safe replay status on this host

The read-only preflight passes source identity and two-device inventory but
fails closed on 17 missing runtime artifacts: the Python environment, compiled
XPU extensions/device libraries, graph-safe FlashAttention package, and pinned
oneCCL runtime. This host has 15 GiB of system RAM. No GPU workload was launched
during this audit.

The prior stock-container exploration is not a replay path: after loading the
weights it exceeded a 9 GiB memory cgroup during warmup and caused one recoverable
BCS reset. It must not be retried or assigned a larger blind memory allowance.
Safe execution remains gated on the items in
`repro/qwen38-27b-autoround-int4-b70/REFERENCE-HOST-HANDOFF.md`, especially a
source-driven runtime bootstrap and measured peak host-RSS/swap bound.
