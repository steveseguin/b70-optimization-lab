# Qwen3.8 Flash-Next TP4 graph attempt 2 admission result

Date: 2026-08-28

Attempt 2 stopped before model or GPU work. The temporary 64-GiB file was
created and activated correctly, but the operating system reported priority
`-1`; the frozen packet required `-2`. The local `swapon(8)` contract accepts
priorities only from `-1` through `32767`, so the intended lower value resolved
to the default `-1`. The supervisor failed closed before deriving or launching
the inner model supervisor. There was no health endpoint, request, quality
gate, replay, or speed row, and this result has no matrix/site credit.

Cleanup passed: the exact file identity remained stable around activation and
deactivation, `swapoff` succeeded, the exact file was removed, and the original
swap layout was restored byte-for-byte. The final journal read succeeded and
contains only the temporary activation record; it has no new OOM or `RxErr`.
No model run directory, inner supervisor directory, listener on port 19675, or
model/worker process remained.

The 23-entry evidence manifest is
[`20260828-tp4-mtp0-current-piecewise-graph-attempt2-primary-evidence.sha256`](../data/20260828-tp4-mtp0-current-piecewise-graph-attempt2-primary-evidence.sha256),
SHA-256 `75effdc56560bd2322d6e34de8b4d9125d534f774c8761efe40f0b3383a2f5a8`.
All entries verify against the immutable resource directory. The structured
receipt is
[`20260828-tp4-mtp0-current-piecewise-graph-attempt2-result.json`](../data/20260828-tp4-mtp0-current-piecewise-graph-attempt2-result.json).

Nothing is replaced or lowered. A fresh attempt may change only this admission
detail to supported priority `-1`, plus the required fresh attempt/port/path
identities. The model/runtime/graph/cache/request protocol remains unchanged.
