# 2026-10-19 — interrupted Nemotron window; replay deferred

**Status: attempted, interrupted and unqualified. Owner deferred Nemotron.**
The prior OMP account overstated the cause and prescribed unsafe recovery steps.
Its original text is retained as [superseded evidence](../data/2026-10-19-nemotron-window-review/superseded-omp-note.txt),
with a [review receipt](../data/2026-10-19-nemotron-window-review/review.json).

## Established observations and remaining uncertainty

- OMP stopped the Turin ctx stack for an approved replay window. Its transcript
  reports stopping earlyoom to work around a broad process-name match.
- The previous boot's journal shows Gemma listening on card 1 at 22:38:46 EDT,
  starting its card-0 replica at 22:39:08, and Nemotron starting at 22:39:35.
  Turin booted again at about 22:45. The checked kernel-journal excerpt has no
  corresponding xe hang, panic, OOM or reset diagnosis. Concurrent launches are
  established; their causal role and the reboot trigger remain unresolved.
- The [campaign script](../experiments/qwen38-27b-b70/scripts/longrun-campaign37.sh)
  **manages the server and proxy**. It has **no EXIT or signal trap**. Its final
  Gemma restore is ordinary sequential code, conditional on RESTORE and fault
  checks. A service stop does not prove that code ran. The original claim that
  stopping campaign49b triggered an exit trap is withdrawn.
- Turin has about **15 GiB host RAM**, not 1.25 TB. The transcript's explanation
  of fast startup as retained page cache after reboot was unsupported.
- OMP deleted the partial r1a directory before this review. This lost useful
  failed-run evidence. No qualified performance, quality or repeat result is
  available from this attempt. Preserve all future failed attempts and use a
  new attempt ID; do not classify the interrupted attempt as never launched.

## Restoration and current ownership

OMP restored FP8 at :18196 using c49b-a3 and the proxy at :18200. Its campaign
restart failed because SUDO_ASKPASS was missing. Parts of the old environment
are documented in the campaign notes, but a blind rerun is unsafe: the script
refuses existing receipts and occupied ports and has no durable queue resume.
Its original 1.6 GiB guard environment was also omitted from the restore script
(the launcher default is 2.0 GiB), so this was not an identical restoration.

At 23:29 EDT the server and proxy units were active, campaign49b was inactive,
Gemma was stopped, and earlyoom was active. Another actor stopped the proxy at
23:30:30 and the FP8 server exited cleanly at 23:30:38. Both endpoint checks then
failed to connect. The review made no service changes; concurrent Turin edits
were left alone. Verify live ownership again before any subsequent operation.

## Requirements for a future authorized attempt

Keep Nemotron deferred. Before reopening it, review the launcher against current
host policy, recover the exact runtime identity, resolve model/service ownership
and all lifecycle hooks, and preserve complete unit argv, environment and stop
settings. Correct the earlyoom process-detection false positive rather than
turning off the protection. Do not automatically mask owner services, change
memory/power settings, restart servers after faults or reboot the host.

Launch any future approved long task in an explicitly configured transient
service or detached supervisor, with logs and a unique evidence directory.
An SSH disconnect alone does not establish whether its remote child survived;
check actual process/cgroup state. Retain faults and halt new requests as required
by the owner's standing instructions.
