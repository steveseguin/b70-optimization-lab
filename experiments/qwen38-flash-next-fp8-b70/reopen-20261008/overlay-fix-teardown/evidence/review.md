# Independent CPU review — 2026-10-09

The owner's requested ordering review ran through subagent `review_order`.
It read the production plan and exact overlay/source, then reviewed the candidate
and re-reviewed the corrections. It made no changes or device calls.

Findings resolved before sealing:

- Restore default entry signals, but retain cooperative engine/worker handlers
  throughout cleanup; callbacks only latch intent, monitors publish STOP.
- Finish/unwind RPC and initialization frames before freeing their aliases;
  wake blocked dequeue and suppress repeated signal exceptions.
- Release expert tables/UVA aliases, including original/restored parameters
  and generic `p.data`, while explicitly retaining host owners.
- Close PLE memoryview/mmap before slabs and clear strong global/model owners.
- Keep transfer-service -> runner -> XPU-pool -> distributed-group order;
  only issue final rank receipts after that order and final cache drains.
- Publish partial runner early; release workspace/rotary/static globals even
  if runner construction was never reached.
- Park failed release unconditionally, even if failure diagnostics raise.
- Pipe-close errors must not skip worker cleanup.

Final review: no remaining blocking ordering issue for synchronous V2 Screen 1b.
Native queue destruction, fatal crash/OOM/SIGKILL and complete native partial-init
behavior remain unproven. Review is source/CPU evidence, not operational approval.

Subagent `controller_patch` separately implemented/reviewed controller copies and
ran eight AST-extracted GPUWorker/XPUWorker shutdown tests with fake services,
allocator and Torch APIs. It verified calibration's combined receipts/container/
kernel gate and noted that one kernel postflight cannot exclude delayed faults.

Late parent review also found and closed a monitor/main shutdown race: both
callers now serialize and wait for worker exit. Failed-startup pipe errors cannot
skip the unready-child wait or hide an already-started child handle. CPU tests
exercise concurrent parent callers and the actual startup-finally block.
