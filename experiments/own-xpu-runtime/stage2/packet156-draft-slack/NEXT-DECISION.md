# Continue through packet152's design dispatch

The [dispatch](../packet152-segment-prep/PLAN.md#verdict-to-build-dispatch)
requires a large *specific removable or overlap bound*, not just a broad wait.
After rejecting the specified hidden-work insertion, the other prepared
designs were checked. None is newly admitted by packet154.

| Design | Evidence now available | Disposition |
| --- | --- | --- |
| capture_snapshot | Packet150's 0.743 ms broad scope justified packet153. Its completed B bracket is exact, 0.0567% control drift, but static descriptors improve only 0.3456%/0.3533% over the fastest control. Its own `candidate_qualified` is false. | Existing work has answered this particular mechanism. Do not duplicate the build or borrow the whole snapshot scope as a saving. [Observed report identity and rates](evidence/next-plan-snapshot-result.json). |
| merge_handoff_waits | Packet154 confirms draft issue/completion/publication dominates rank0's wait. The remaining transport part is about 0.05 ms/interval in smoke. | No transport-only +2% build. This is precisely the PLAN's subcause restriction. |
| token_prep | Completed packet150 control median 0.122935 ms/cycle; no new large token-work observation. | Below the admission threshold before staging/join cost. |
| suffix_head | Completed packet150 control median 0.310820 ms/cycle for the entire head; the proposed argmax/pack epilogue removes only its small tail. | No supported +2% epilogue build; do not reopen partition/placement sweeps. |
| draft_wait / remote draft | Exposed draft work is real. This packet bounds the proposed host suffix-slack window far below the required saving. | Close this host-boundary arm only. Do not translate draft latency into available suffix slack. |

The remaining draft question is **actual work inside the command**, or a
different earlier device-enqueued boundary whose legal window has not been
measured. The packet122 historical per-class event samples put hidden norm
plus projection at roughly 0.064–0.069 ms, excluding copy/host overhead and on
a different runtime identity. That is secondary diagnostic context, not a
current complete-branch ceiling, and not grounds to re-run its closed HC/load
micros. Keep this limitation explicit.

A future earlier enqueue design must first correlate actual prefix completion,
suffix publication and the *complete* hidden branch at the proposed queue
boundary; `b_completion.end` is host drain return, not device finish. It needs
enough net exposed saving to clear packet147's 0.423078 ms/hit threshold and
cannot borrow prefix compute overlap on one CCS. Until then, the dispatch's
"no device candidate admitted" outcome applies. This is a missing measurement
for a different mechanism, not permission to launch a speculative test or an
assertion that the draft lane is finished.
