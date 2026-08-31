# Qwen3.8 AutoRound INT4 TP2 all-reduce device-sync R4 preregistration

Date: 2026-08-30

Status: **preregistered before either R4 model request**

## Question

R3 proved that the current MTP0 TP2 target is not repeatable in eager (9/12)
or compiled (4/12) execution. Production-shape INT4 GEMMs were then exact
within and across eight fresh processes. Does a whole-device drain immediately
after the existing oneCCL `Work.wait()` make two fresh compiled servers repeat
all complete outputs?

This is a causal localization, not a proposed production recipe. The treatment
is deliberately expensive.

## Frozen identity and only treatment

- two local B70s, physical IDs 0 and 1, TP2, AutoRound INT4, MTP0;
- base image ID
  `sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136`;
- diagnostic image
  `neural-download/vllm-openai-xpu:qwen38-autoround-allreduce-sync-diagnostic-r4`,
  ID `sha256:aa212832d5ba6d88d2fa47d1ce9b08ce3862e90bbd4aa57156d6eaafef14f1d2`;
- communicator SHA-256
  `c9a356a5a11006206ae83da9c09fd6cee86e9cd6f65e8d8d877bfe08d0762373`;
- only source change: `torch.xpu.synchronize()` immediately after the existing
  asynchronous all-reduce `Work.wait()`;
- compiled Inductor with XPU Graph off, prefix caching off, FP16 activation/KV,
  deterministic Inductor, native GDN fallback, persistent scratch, and the
  existing INT4 pad;
- the same fixed 12-prompt/six-class suite, each prompt once, complete token
  IDs, zero cached tokens, temperature 0, and natural 512-token cap.

## Ordered experiment and decision

Run two fresh compiled arms (`sync-A`, then `sync-B`) with independent empty
compile/evidence roots. Each must pass direct model/image/file verification,
the complete realistic workload, canaries, clean shutdown, and the kernel
journal gate.

A causal positive requires **12/12 complete token-array equality** between A
and B. Anything less rejects the collective-boundary hypothesis. Even a 12/12
result is diagnostic only: do not promote its speed, authorize MTP, or publish
it. A positive authorizes a narrower dependency/fence screen that removes the
whole-device drain.
