# Qwen3.8 Flash-Next FP8 A50 strict-AER guard negative

Date: 2026-09-01
Status: bounded guard-policy negative; zero quality or speed credit

A50 selected and validated the complete external checkpoint, proving the USB
model authority is usable. During registry/config startup the local NVMe read
counter remained exactly unchanged, but its corrected endpoint counter rose
from `63` to `64`. The inherited any-increment rule stopped the arm. Teardown
removed the isolated RPC directory while model-architecture inspection was
still unwinding, so vLLM also reported a secondary `FileNotFoundError`; that is
not an external-checkpoint incompatibility.

No shard load, healthy endpoint, or request occurred. Memory stayed above 126
million KiB, swap stayed disabled, root-port AER stayed zero, and four-device
postflight was healthy after the short-lived helpers exited.

This result proves that a literal-zero corrected-event policy is not usable on
the currently noisy link even when the model performs no local-NVMe reads. A51
keeps the external checkpoint and replaces that single rule with a bounded,
measured policy: at most 64 new corrected endpoint events, at most 8,388,608
additional NVMe read sectors (4 GiB), zero root-port increment, and immediate
failure on any non-corrected link report or existing memory/swap/device gate.
