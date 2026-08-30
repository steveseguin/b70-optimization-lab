# Qwen3.8 Flash-Next FP8 TP4 MTP0 greedy-trace A8 closeout

Date: 2026-08-29
Status: infrastructure-negative; host stopped during worker initialization

A8 passed its model, staged-runtime, four-card idle, and four-rank XCCL
preflight gates. The API process and engine coordinator started. Worker rank 0
reported distributed initialization at 23:28:26 and rank 1 at 23:28:31. Ranks
2 and 3 never reported initialization, no checkpoint-shard load began, server
health never passed, and the host stopped responding before the launcher could
write a controlled closeout.

The reboot preserved a 49-line server log and an empty health-poll file. There
is no greedy trace, client receipt, exact-4K response, model-load receipt,
throughput row, or quality result. A8 therefore grants no performance,
correctness, deployment, or coverage credit and changes no protected result.
The persistent prior-boot journal ends before the last server-log timestamps,
so it contains no attributable A8 kernel diagnosis. Older B70 records and
corrected local-NVMe receiver reports in that boot predate A8 and are not
assigned to it.

Post-reboot checks found all four B70s enumerated and idle at 42.875--42.883
MiB, approximately 120 GiB host memory available, no model process or port
19680 listener, and clean optimization/runtime repositories. The external NTFS
drive was manually remounted and the interrupted run root was intact.

Primary evidence SHA-256 values:

- `server.log`: `69d3fed4e5af6b3e89c4350a0cfb1cf066cadf14662ccbca45fab869f1d48b7c`;
- `identity.txt`: `eb43eeee0e72ffb368f25909a792e71f3b89d67a8a30b0c157a72c54d92bfe3b`;
- `xccl-tp4-preflight.log`: `ac3aa63d1840c12432839085087b22e1ca15e5c3a014d7ef60aedd479b67c5d2`;
- `staged-runtime-preflight.txt`: `7ea286e60b946c6d5ed9caaad0090a41b3f94ac52c2c32b16547983250f6a004`;
- empty `health.json`: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

The exact opt-in trace patch remains preserved, but it is removed from the
active runtime by source commit `e5137bfd8`. The resulting files are identical
to the known-good pre-trace source commit `1372c62d9` for every path the trace
changed. Do not retry A8 unchanged.

The active goal returns to a trace-free TP4 short-context placement: keep the
large PLE/ngram table in host RAM, fit all practical remaining weights in VRAM,
qualify reliable lossless MTP0 decode at 4K, and only then add MTP.
