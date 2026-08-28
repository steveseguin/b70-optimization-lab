# Qwen3.8 Flash-Next TP4 graph attempt 6 result

Date: 2026-08-28
Status: closed before model start; no website or performance credit

Attempt 6 stopped at the exact fail-closed gate it preregistered. The derived
launcher enumerated live process directories, then its schema-v2 structured
runtime scan reached PID `1922600` after that short-lived process had already
exited. The first identity read, `/proc/1922600/stat`, returned ENOENT. The
receipt contains zero runtime conflicts, one read error with no observed
identity, and 506 successfully scanned processes. Schema v2 returned `rc=2`,
so the launcher exited before setting or validating the compile-thread
treatment and before starting vLLM.

This is a procfs enumeration race, not a model/runtime failure and not evidence
that a conflicting server was present. It also does not validate the proposed
classifier change retrospectively: attempt 6 remains an exact schema-v2
pre-model negative. The prospective schema-v3 rule is deliberately narrow:
only initial `stat` ENOENT after numeric-directory enumeration is recorded as
`vanished_race` and skipped. If initial `stat` succeeds, every later missing or
unreadable required field, stat/status mismatch, or changed identity remains a
hard `rc=2` error.

No model process started, no shard loaded, no graph compilation began, and no
health request, client, quality gate, replay, or speed row ran. The declared
`TORCHINDUCTOR_COMPILE_THREADS=1` treatment was not reached. Consequently this
attempt changes no matrix cell, website coverage, deployment grade, graph
claim, or captured speed.

Cleanup was exact. The temporary 64-GiB swap recorded zero use, swapoff and
unlink passed, the original swap layout was restored byte-for-byte, the final
terminal and runtime scans were clear, port `19680` was absent, and all four
cards returned to roughly 42.88 MiB used. The eight watchdog samples never
dropped below 114,619,512 KiB available host memory.

The 50-file ext4 resource tree was mirrored byte-for-byte to the declared USB
archive and its manifest verifies. The combined resource-plus-supervisor
manifest contains 73 entries and has SHA-256
`dbb0bd2f9549e96e8acef9a423bb2ea3b6357299cb7d5e2f525f8b93f65b3b29`.
The full structured closeout is
[`20260828-tp4-mtp0-current-piecewise-graph-attempt6-result.json`](../data/20260828-tp4-mtp0-current-piecewise-graph-attempt6-result.json),
and the tracked manifest is
[`20260828-tp4-mtp0-current-piecewise-graph-attempt6-primary-evidence.sha256`](../data/20260828-tp4-mtp0-current-piecewise-graph-attempt6-primary-evidence.sha256).

The next authorized graph arm must be a fresh attempt 7 on port `19684` with
new state, ext4 resource/swap, USB run/cache/supervisor/archive paths, the
schema-v3 classifier and its bounded churn fixture, and the otherwise unchanged
attempt-6 model/runtime/client/resource contract. It is not authorized to
launch until its complete hash chain passes independent audit.
