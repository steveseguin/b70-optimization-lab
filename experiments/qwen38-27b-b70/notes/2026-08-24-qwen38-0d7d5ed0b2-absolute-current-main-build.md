# 0d7d literal-current zero-overlay build

Date: 2026-08-24. Status: **static build and archive pass; GPU
qualification pending.**

The general current-main builder ran once from clean pushed `main` at lab
commit `2f0441e9d`. It resolved and retained these literal identities through
the post-archive freshness seal:

- vLLM `0d7d5ed0b2b61da53f682534f1754fe7d0251a34`, tree
  `32a84ef59ace9ebad6200dd71d658cf986f416f1`, package
  `0.26.1rc1.dev1160+g0d7d5ed0b.xpu`;
- XPU kernels `baaa05bb4e92901219a5a072dd63f2474896f6d1`, tree
  `e7e7d1063f232a383c98c1820cebb94c45b4906e`, package
  `0.1.dev1+gbaaa05bb4`;
- official nightly base/index digest
  `sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`.

Both zero-source-overlay images passed wheel identity, import, extension,
Torch-schema, DSO dependency, known pip-check, source-shadowing, label, and
static-receipt gates:

- stock-base-kernel control
  `sha256:38ec94fd09ec93e4e698aefcf02e0db37ff54c964db2ca42175db52886d14662`;
- both-current candidate
  `sha256:bbaa702fa0fd4e1d2b9e178a61747657ec35fa5dc83655903f13925a8b83c23d`.

This build is the first to carry the explicit performance-asset preservation
gate added in `2f0441e9d`. The literal source, wheel, installed package, image
labels, import receipt, source identity, and aggregate build receipt all bind
`vllm/model_executor/determinism/batch_invariant_configs.py` to SHA-256
`e47b18d9394c61fd105e4db51108d72fe1e68d4a2043a8ba62c0af0237453128`.
Both former `model_executor/layers/batch_invariant*.py` members are rejected.
No decision file, compiled graph, old cache, or source patch was applied.

The normal aggregate receipt is byte-identical in the ext4 build root and USB
archive at SHA-256
`3fb8db843817624948833e53d49f41839a63703502649c9151be1c1b18e38c2e`.
The 14-file USB `SHA256SUMS` battery passes and has SHA-256
`fe0bf831c91beb95d2711e853406450130a659062bbeccdef5cd9e45b99e9930`.
The tracked receipt is
[`2026-08-24-qwen38-0d7d5ed0b2-absolute-current-main-build.json`](../data/2026-08-24-qwen38-0d7d5ed0b2-absolute-current-main-build.json).

No GPU, model load, graph compile, benchmark, canary, or quality request ran.
This creates no speed claim and changes no protected result or floor. Before a
newly named TP1 packet launches, re-resolve vLLM, XPU-kernel, nightly, and lab
identities. If any engine identity moved, close this build stale and build its
successor. If they remain exact, qualify stock-kernel attribution and then the
both-current zero-overlay lane without lowering the frozen TP1 gates; only a
full pass authorizes fresh decision remapping, TP2, then TP4.
