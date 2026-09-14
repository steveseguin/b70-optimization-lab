# One-pass state guard CPU edge cases

The parent79b4 and candidateba8939 guards agreed on all48 acceptance comparisons
across24 cases, with device checking disabled and enabled. Cases covered shared
modules, parameter/buffer/cross-registry aliases, None registrations, empty
state, invalid dtype, meta-device mismatch, and late local/global hooks.
The checks did not change registered metadata. Multiple simultaneous errors'
priority was not part of the contract.

The harness extracted only the two pinned `_validate` methods and applied them
to actual native32-wide BasicAVTransformerBlock objects with video feedforward
bias disabled and audio bias enabled. It did not call block forward, construct
a compiler, load model weights, or execute on XPU. Explicit CPU admission and
Comfy CPU arguments preceded native imports. XPU initialization remained false
before and after; peak process RSS was787172KiB.

Harness: `../scripts/test-onepass-state-cpu.py`, SHA256
`a6c33bd15af8b7bf3f436594bf7c25b8cc1126ee123a9bf402a38ce8435920c9`.
Receipt/log: `../data/onepass-state-cpu-edges-01.json` and matching `.log`.
Full source snapshots and case records remain in
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/onepass-state-cpu-edges-01`.

An initial invocation selected an already occupied evidence directory and
refused before Torch import; `../data/onepass-state-cpu-01.log` preserves that
refusal. Existing evidence and the live application were untouched. The
subsequent fresh-directory run completed with exit0. These are metadata guard
tests, not native output equivalence or speed measurements.
