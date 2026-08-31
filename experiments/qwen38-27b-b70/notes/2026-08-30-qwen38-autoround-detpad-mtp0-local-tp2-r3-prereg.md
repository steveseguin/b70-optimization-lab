# Qwen3.8 AutoRound INT4 MTP0 local TP2 R3 repeat localization

Date: 2026-08-30

Status: **preregistered before either R3 model request**

## Question

R2's compiled arm was 77.137% faster but matched its eager oracle on only
4/12 complete token arrays. Is that rejection caused by within-mode TP2
nondeterminism, or are eager and compiled modes each repeatable but
numerically different?

## Frozen inputs

- the same two local B70s (physical IDs 0 and 1), TP2, AutoRound INT4 target,
  MTP0, FP16 activations/KV, XPU Graph off, and prefix caching off;
- image ID
  `sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136`;
- complete fixed 12-prompt/six-class realistic suite, each prompt once,
  temperature 0, natural 512-token cap, complete token IDs, and cache zero;
- R2 eager performance SHA-256
  `216efe21ec193ed50fc3fa453fcf2161c864aac5431d579ece24a35e5dc05d2a`;
- R2 compiled-A performance SHA-256
  `3a8ffa399c64d3a34d8703eb2a9f4cee2d2076cef8d7b79d74c822953914f6ed`.

## Ordered experiment

1. Run one fresh eager repeat (`eager-B`) with a new empty cache/evidence root.
2. Run one fresh compiled repeat (`compiled-B`) with another empty
   cache/evidence root.
3. Compare all complete token arrays: R2 eager vs eager-B, R2 compiled-A vs
   compiled-B, and eager-B vs compiled-B.

Every arm must independently pass direct model verification, image/extension
identity, the complete realistic workload, zero cached tokens, canaries,
bounded cleanup, and the kernel-journal gate. No prompt subset, retry, warm
fixture, or early result is authorized.

## Decision rule

- If eager and compiled each repeat 12/12 but disagree cross-mode, localize
  compiler numerical semantics; do not call the lane nondeterministic.
- If compiled fails its same-mode repeat, prioritize the compiled TP2 race.
- If eager also fails, prioritize the shared TP2 runtime/collective/state path.

All R3 speeds are diagnostic. R3 cannot promote MTP0, authorize MTP, or create
a public headline regardless of parity.
