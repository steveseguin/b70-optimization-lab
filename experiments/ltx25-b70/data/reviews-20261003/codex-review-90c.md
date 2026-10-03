# Codex read-only review, packet 90c (2026-10-03)

Final answer of `codex exec -s read-only`; the prompt and the fixes that followed are in the packet build notes.

Confirmed defects, most severe first. Paths below are under `experiments/ltx25-b70/scripts`.

- **Failed tail sentries can still produce exit 0.** `pipeline_sampler_node.py:209–217` writes `finite:false` without raising; validation occurs when collected (`:350–354`). The final two samples remain uncollected. `run-campaign-90c.sh:98` checks only marker existence, so those failures pass.
- **The runner can hang indefinitely.** Health requests have no timeout (`run-campaign-90c.sh:143,146`). Separately, a failed `touch` at `:70` leaves it waiting for a watcher whose only exit condition is that file appearing (`:55`).

**A)** Finding 1 is substantially fixed for the intended single-client run: all campaign sample/decode jobs require markers, and a server still alive after the stop deadline returns 7 (`run-campaign-90c.sh:91–135`). It is not an unconditional safety guarantee—see C. Finding 2’s ordinary event-creation/recording exceptions are caught (`ltx_graph_capture.py:622–645`). Finding 3 is fixed by merging segments across receipts (`analyze-phases.py:128–140`). Finding 4 is fixed: no steady rows returns 2 without fallback (`:273–279`).

**B)** Markers **can block workers**: they synchronously open/write/close files before the worker sets `job.done` (`pipeline_sampler_node.py:48–63,217`; `pipeline_decode_node.py:47–62,249`; `ltx_pipeline.py:143–148`). Timer locks can also block (`ltx_graph_capture.py:606,615`). Both can shift cross-worker GPU submission timing. Neither explicitly reorders a stream’s model operations; replay remains once between begin/end (`:940–942`). Ordinary exceptions are caught; “never raises” is not absolute: `_busy_disable` itself calls unguarded `repr(error)` (`:600`), and `BaseException` is not caught.

**C)** Exit-path trace:

- Preflight/identity/mode refusals: 8; observed fault: 4.
- Warm failure: preserves its nonzero status. Endurance failure other than 3: preserves status, leaves server running.
- Shutdown uncertainty: fault 4, queue 5, missing markers 6, identity/stop failure 7.
- Successful shutdown: preserves endurance 0 or mismatch 3 (`run-campaign-90c.sh:138–180`).

Only one explicit signal exists: `kill -INT $PID`, with no escalation (`:127`). However, queue-check→signal and identity-check→numeric-kill races remain (`:124–127`): another client can enqueue work, or the PID can exit and be reused. Thus **absolute quiescence and target identity at signal time are not guaranteed**. Commit failures explicitly continue (`:48–50`); sync and kill statuses are unchecked. A failed kill followed by an absent process returns success (`:127–135`).

**D)** No direct change to tensor writes, RNG, or arithmetic was found. Scheduling perturbations could expose existing concurrency bugs; static review cannot establish byte identity. Existing phase-event operations also remain unguarded (`pipeline_sampler_node.py:195–200,232–237`), even with busy windows disabled.

Read-only review; no servers, GPU operations, or file modifications.
