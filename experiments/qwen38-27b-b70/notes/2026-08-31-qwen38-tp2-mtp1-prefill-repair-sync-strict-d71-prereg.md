# D71 preregistration: synchronized real-prefill repair after reboot

Date: 2026-08-31

D70 proved the dummy bypass and profile-only barriers are correctly scoped, but
rank 1 lost its device asynchronously during the first real repaired prefill.
D71 changes only
`VLLM_XPU_QWEN38_PREFILL_PROJECTION_SYNCHRONIZE` from 0 to 1. The hook's
existing barriers execute before and after repaired QKV, output, gate/up, and
down projections only when `32 < M < 512` on a real request. Dummy runs bypass
the repair and decode rows are outside the band, so neither pays this cost.

D71 may run only after a full reboot and independent deterministic compute gate
on both local B70s. It otherwise preserves D70's immutable image and hook, TP2,
MTP1, eager mode, startup bound, device order, memory limits, exact startup
receipts, full 12-prompt/512-cap varied suite, cache-zero rule, complete token
IDs, objective canaries, and frozen D59r MTP0 oracle.

A pass requires all twelve complete arrays to match the oracle, all strict
quality/cache gates, exactly 1,040 decoder receipts both before and after
requests, four receipts per sampler stage, both health checks, clean teardown,
and a clean timestamp-bounded kernel delta. The primary rate remains the median
of prompt-class medians over conventional token-1-to-100 intervals. Any failure
rejects D71 without retry or promotion; a surfaced projection-stage exception
is localization evidence only.
