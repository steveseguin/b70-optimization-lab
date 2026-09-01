# Qwen3.8 TP2/MTP1 profile-only decoder-sync D67 confirmation

Date: 2026-08-31

D67 passed the exact zero-request startup qualification. The immutable
profile-only image emitted 1,040 decoder `begin` and 1,040 matching `pass`
receipts during the one true profile forward across two ranks. Each of all nine
dummy-sampler stages produced exactly four pass receipts. The later warmup
forward completed without decoder barriers, both HTTP health checks passed,
teardown was clean, and the timestamp-bounded kernel log contains no GPU, OOM,
filesystem, or I/O fault. No inference request was served.

This confirms a deployable-scope startup mechanism: synchronize the first
profile forward, clear the worker-local marker after vLLM's existing final
device sync, and leave later warmup and serving forwards unsynchronized. It is
not performance or quality evidence. D68 must restore projection repair, run
the complete strict varied suite, match every complete token array to the
frozen TP2/MTP0 oracle, pass canaries/cache-zero gates, and prove the decoder
receipt count does not increase while serving requests.

Raw evidence:
`/mnt/fast-ai/bench-results/qwen38-tp2-mtp1-profile-only-decoder-sync-20260831-d67/`.
