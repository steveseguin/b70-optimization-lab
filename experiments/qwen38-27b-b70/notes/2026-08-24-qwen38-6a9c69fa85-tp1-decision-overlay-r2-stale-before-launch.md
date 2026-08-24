# 6a9c TP1 decision-overlay r2 closed stale before launch

Date: 2026-08-24. Status: **closed stale before launch; never launched.**

The fresh-root r2 packet passed its static, preservation, and fail-closed
audits, but it had not been committed and never crossed the prelaunch gates
into a campaign. The final independent freshness audit at
`2026-08-24T21:44:48Z` resolved live vLLM `main` to
`0d7d5ed0b2b61da53f682534f1754fe7d0251a34`, not the frozen build identity
`6a9c69fa851389dcf1ee5d3a2363e27af665d26d`. XPU-kernel `main` remained
`baaa05bb4e92901219a5a072dd63f2474896f6d1`, the official nightly index
digest remained
`sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`,
and lab `HEAD`, cached `origin/main`, and live `origin/main` all remained
`d977218b8c44f4c9f87ccf01e60cd3f0fe323e5d` at the veto point.

The successor is three linear commits after 6a9c. It refactors the upstream
batch-invariance package from `vllm/model_executor/layers/` to
`vllm/model_executor/determinism/` without changing the tuned-config file's
bytes (SHA-256
`e47b18d9394c61fd105e4db51108d72fe1e68d4a2043a8ba62c0af0237453128`),
sizes the FlashInfer fused-allreduce/RMSNorm workspace for the wider of the
target and draft models under TP speculative decoding, and closes an audio
input size-limit bypass. The range changes 17 paths with 105 insertions and 18
deletions. It includes runtime, determinism-import, distributed-fusion, and
speculative-decode-adjacent paths, so literal-current policy requires a new
zero-source-overlay build and fresh qualification rather than waiving the
delta.

The TP>1 commit is relevant to the wider matrix, but it does not by itself
prove that the observed XPU TP>1 speculative-decode worker-init broadcast hang
is fixed. Its `AllReduceFusionPass` implementation is imported only for CUDA,
while XPU disables `fuse_allreduce_rms`; the XPU failure also occurred before
serving. Treat it as a reason to retest the newest base after target-only
TP1/TP2/TP4 preservation, not as a result.

The r2 wrapper was exercised only through fail-closed static smokes: two
invalid-mode smokes exited 2 at the usage gate, and one intentional
dirty-worktree `all` smoke exited 1 at the clean-lab prelaunch gate after its
read-only predecessor checks. None created a root, acquired the campaign
locks, invoked the hardware gate, or exposed a GPU. Both exact r2 roots remain absent, ports
`19789`-`19791` are unbound, Docker has no running container, no model process
or render-node holder exists, and no r2 model load, cache compile, canary,
benchmark, quality battery, or GPU work ran. This closeout is not performance
or quality evidence and changes no protected speed.

Keep the exact preregistration and wrapper as stale provenance. Their SHA-256
values are respectively
`67f60a5a8eeb76dcd81844abbf93c0478441a083ce0491490c0302af4cf32d6b`
and
`bea6ce4fddce80d02f03fc123bd2247c28398c151e4ecdb82882fba50feeda16`.
The wrapper's floors remain `30.2178 tok/s` diagnostic and
`30.31067504052998 tok/s` strict. It must never be invoked, repinned, resumed,
or relabelled for the successor.

The separately audited shared strict runner adds an opt-in `frozen-local` lab
Git policy while retaining the prior continuous policy by default and keeping
all live vLLM, XPU-kernel, nightly, image, model, cache, quality, and speed
gates. Preserve that general protocol improvement for a newly versioned
successor packet. One audit hardening carries forward: if a successor promises
that the actual failed predecessor remains live-gated during model arms, call
its full predecessor verifier from `verify_inputs`; otherwise explicitly make
the frozen predecessor snapshot the in-arm source of truth.

The 6a9c r1 evidence remains sealed. Its untreated run completed with
diagnostic `30.27858669748398 tok/s`, strict A/B
`30.26782494070049 / 30.27119782672338 tok/s`, and all non-speed gates green.
Decision-overlay r1 passed only its diagnostic at
`30.268740193465128 tok/s`; strict A/B and the quality battery never ran. The
38-decision candidate is therefore not qualified. The complete protected
performance ledger SHA remains
`e6ee2cb9908ce940087788243eac5b544c0d2831b94efa47fe6441232c740e8f`.
All 78 TP2 and 152 TP4 decisions remain byte-preserved under manifests
`65c574c24d24804d250e5179e9a202ec9e77e8c5740cea121b7660d8ee854757`
and
`a2df36339567d2619e024351deeca98970ebf92497db0148eac0de7dd5df3ba2`;
neither is discarded or blindly applied to the successor.

The next action is to build `0d7d5ed0b2b` or any newer successor from literal
vLLM `main`, exact-current XPU kernels, and the live official nightly with zero
source overlay. The build and qualification must recognize the new
`vllm/model_executor/determinism/batch_invariant_configs.py` wheel path. Then
run target-only TP1, derive a fresh path/`configs_hash` compatibility census,
and qualify any decision-only overlay into a new compile cache. Only a full
current TP1 pass authorizes TP2 zero-overlay plus its remapped 78 decisions;
TP4 zero-overlay plus its remapped 152 decisions follows. No captured floor or
historical high may be lowered or replaced.

The structured closeout is
[`2026-08-24-qwen38-6a9c69fa85-tp1-decision-overlay-r2-stale-before-launch.json`](../data/2026-08-24-qwen38-6a9c69fa85-tp1-decision-overlay-r2-stale-before-launch.json).
