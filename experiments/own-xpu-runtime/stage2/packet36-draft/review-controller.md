# Independent controller timing and race review

Reviewer: Codex subagent `/root/timing_review`, source review before and after implementation.

DRAFT(p) starts immediately after rank1 has completed and accepted HALF(p-1), using confirmed x_p. It overlaps rank0 completion or redo of p. The next rank1 command waits for the DRAFT reply; slot1 is not overwritten while rank1 consumes it. Draft reads rank1-local final streams while rank0 may write slot0. Shared metadata is copied before socket reply and read before another rank1 command, validating sequence and predicted position.

Hit cycle: max(A,B+D). Miss cycle: max(max(A,B)+A_redo,B+D), plus IPC/accept/handover overhead. Starting DRAFT only after rank0 resolves yields D+max(A,B). Starting with an unconfirmed guessed embedding would require draft rollback and is excluded.

Successful draft rows form the same confirmed chronological sequence regardless of rank0 speculation. There is no artificial row before H0+x1.

Found and fixed: persistent disabled-provider assertion; non-stalling stall injection; fault-injection speed field; draft time counted as rank1 idle; missing wait/cycle fields and final-row annotations. Declared provider errors recover only after drain; an actual stuck kernel cannot share a safe fallback with target execution and follows owner fault rules.

No device or heavy CPU tests were run in this review. Gate evidence is separate.

Final coordinator review found and closed KD wrapper gaps: bind the measured
K2 dispatch, build/source receipt, input artifacts, capture table and retained
fixture bytes; require safe native teardown; monitor anonymous memory; poll
kernel faults immediately before each owner and throughout failure draining.
The W wrapper admits both native allocation censuses before its first HALF.
The reviewer reread these fixes and reported no remaining blocker in the new
KD path. Actual device residency and driver overhead remain unmeasured.
