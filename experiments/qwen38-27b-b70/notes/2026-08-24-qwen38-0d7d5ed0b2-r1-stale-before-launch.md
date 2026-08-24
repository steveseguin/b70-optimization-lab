# 0d7d5ed0b2 r1 closed stale before launch

Date: 2026-08-24. Status: **closed stale before launch; never launched.**

The 0d7 both-current zero-overlay TP1 packet passed its static, safety,
preservation, and independent audits. The final freshness check at
`2026-08-24T23:08:37Z` then resolved live vLLM `main` to
`d154d90d6c4bcf26a0c78ac4f3e43621c14333ba`, not the built
`0d7d5ed0b2b61da53f682534f1754fe7d0251a34` identity. XPU-kernel main
remained `baaa05bb4e92901219a5a072dd63f2474896f6d1`, and the official nightly
digest remained
`sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`.
The freshness gate therefore vetoed the run. No hardware gate, model load,
canary, timed benchmark, quality battery, or GPU work ran.

The successor is the direct child of 0d7. Its single commit is `[Model Runner
V2] batch-sharded sample (#50465)`: 19 paths, 1,781 insertions, and 22
deletions. It directly changes `vllm/model_executor/models/qwen3_5.py` and adds
an optional tensor-parallel batch-sharded sampling path. The option defaults
off and would reject the protected one-request TP configuration if explicitly
enabled, so it is not silently added to the baseline. It is relevant to the
later multi-request TP matrix and deserves a separate preregistered experiment.

The forward-port checks are green. The exact upstream batch-invariance config
is still present at
`vllm/model_executor/determinism/batch_invariant_configs.py` with SHA-256
`e47b18d9394c61fd105e4db51108d72fe1e68d4a2043a8ba62c0af0237453128`;
its two required companion files remain present, both legacy paths remain
absent, and the reusable Rust inputs are unchanged. The 78-file TP2 and
152-file TP4 decision bundles are unchanged, disabled, and preserved for fresh
compatibility remapping after the newest zero-overlay anchors pass.

The archival packet also carries three safety corrections that must remain in
the d154 successor: image-content probes run only while all campaign locks are
held; the aggregate benchmark check iterates all three arm objects correctly;
and speed medians must be positive, finite, non-NaN JSON numbers with exactly
25 observations. Wrapper failures seal a stage and reason without recording
commands or environment values. These checks do not alter a server argument,
graph mode, cache policy, quality setting, topology, or performance floor.

Frozen packet identities are:

- preregistration:
  `a24cf326e05a5b61bbf021fd5a0a5f3e750845ee5a81a2a72fd36c1d45bcc2e1`;
- strict runner:
  `ec86caef12471185b849a91695fd9dd9fa1e4786771b5ee717c40ff2fae24ecb`;
- qualification wrapper:
  `2e3f438b31b2f182023ab4bd5b1e0c6006c26e60c23a536f2591f49f0b36980e`.

Both frozen roots remain absent, ports `19792`-`19794` are unbound, Docker has
zero containers, no model server or render-node holder exists, and the static
asset probes left no container behind. The probes were network-disabled and
had no GPU device. This is static provenance only, not performance or quality
evidence, and it changes no protected result.

The structured closeout is
[`2026-08-24-qwen38-0d7d5ed0b2-r1-stale-before-launch.json`](../data/2026-08-24-qwen38-0d7d5ed0b2-r1-stale-before-launch.json).
Retain the exact 0d7 preregistration and wrapper as stale provenance; never
invoke, repin, resume, or relabel them. The next action is a fresh zero-overlay
build from d154 or any newer vLLM `main`, exact-current XPU kernels, and the
live official nightly digest. The new build does not replace a speed record:
it must requalify against the existing TP1 floor before fresh TP2-78 and
TP4-152 compatibility packets can be run.
