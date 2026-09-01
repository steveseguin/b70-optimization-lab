# Qwen3.8 TP2/MTP1 dummy-repair bypass D69 startup pass

Date: 2026-08-31

D69 passed the exact startup-only qualification with projection repair enabled.
The immutable image marked every `_dummy_run`; the mounted projection hook
bypassed its M=512 padding only while that marker was active. The first profile
forward completed exactly 1,040 decoder begin/pass boundaries, the later dummy
warmup completed without decoder barriers, and each sampler stage produced
exactly four receipts. Both health checks passed, teardown was clean, and the
timestamp-bounded kernel log contains no GPU, OOM, filesystem, or I/O fault.

No inference request was served, so D69 is not speed or quality evidence. D70
must run the full varied strict suite with the real-request projection repair
active, match all complete token arrays to the frozen MTP0 oracle, pass all
cache/canary gates, and prove the decoder receipt count stays exactly 1,040
after serving.

Raw evidence:
`/mnt/fast-ai/bench-results/qwen38-tp2-mtp1-dummy-repair-bypass-20260831-d69/`.
