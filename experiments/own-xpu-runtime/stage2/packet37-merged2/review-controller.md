# Independent controller and lifetime review

Status: native rank and coordinator reviewed; 11 independent CPU protocol tests and 2 native host-rank fault gates pass. No unresolved controller/teardown finding in the reviewed source; device execution remains unqualified.

Scope: CPU source review only. No device, discovery, compilation, or GPU operation was performed by this reviewer.

## Native rank protocol

The native transfer helper reads/writes fixed size frames in a partial-I/O loop, polls with a deadline, checks cancellation at most every 100 ms while idle, uses nonblocking socket operations, suppresses SIGPIPE, and rejects EOF. Each rank checks a monotonically increasing request sequence. The stop pipe is level triggered and never consumed; readable data or closure remains visible to both ranks. A rank polls cancellation during upload and launch guards. No signal is needed to stop a loading rank.

Rank 0 writes its shared payload only after its own queue drains. Rank 1 obtains its payload through a host-to-device upload, and never receives a speculative request. A candidate must be accepted or undone before the next half. Fixture publication occurs on ACCEPT, so a discarded candidate does not overwrite retained fixtures.

Each process creates its own Device with a single-device backend. Device shutdown preserves the inherited order: drain, graph borrowers, allocations, idle marker, events, queue, context. Failure receipt and failure text precede shutdown. Incomplete native ownership writes retained-owner.json before the deliberate supervisor hold.

## Review observations sent to implementer

- FINISH has no reply: coordinator must wait for process exit rather than wait for a reply frame.
- Every idle/stalled wait must observe stop pipe closure as well as a stop byte; the current native transfer helper does.
- The old packet 29 wrapper sends SIGTERM on deadline; model windows must use the cooperative two-rank stop protocol instead, preserving the no-signal-during-load rule.
- Coordinator must never overwrite the rank-1 input slot until its previous HALF reply; candidate rank-0 output must be copied before rank 0 produces a subsequent output.
- Predictor history must contain only confirmed tokens. On a miss the speculative half must drain before rollback and redo.

These are protocol invariants, not evidence of successful device execution.

## Coordinator review and fixes

Three concrete findings were reported and corrected in the reviewed code:

1. A normal FINISH race: rank 0 could exit before FINISH reached rank 1, and the common liveness check would treat that expected exit as a fault. `finishing` now marks each rank before FINISH, so normal exit is permitted. A forced scheduling test waits for rank 0 to exit before rank 1 receives FINISH.
2. Cleanup after failed teardown validation: resource closure preceded receipt validation, and the catch path would write a closed stop pipe. `closed` makes stop/close idempotent. The test supplies a failed teardown receipt after both ranks exit and repeats the catch path.
3. Handover timing included deliberate delay before reading a ready reply. Native command receive/completion timestamps now distinguish command handover from time spent waiting for the other rank. Aggregate idle-time interval accounting was separately requested to exclude model load and teardown.

The controller copies a confirmed rank-0 slot before starting the next rank-0 HALF, and refuses to overwrite the rank-1 slot while a command remains pending. It starts at most one command on each rank. A speculative result is joined before ACCEPT or ROLLBACK; rollback precedes redo. Confirmed history alone reaches the predictor. Rank 1 receives only confirmed work. At EOS the pending speculative half is joined and rolled back, with no next output emitted. The final requested output does not start an unnecessary next half.

## Independent CPU tests

`test_controller_review.py` uses the real Python Transport with two separate Python process stubs and real Unix socketpairs/shared mappings/stop pipe. The stubs implement framing only; they do not model arithmetic or execute native/device binaries. `review-controller-tests.json` records 11/11 passing tests:

- replies fragmented into three-byte writes;
- truncated frame plus process exit;
- failed rank stops its peer;
- stalled rank reaches bounded timeout and both stop;
- one persistent stop byte stops two idle processes, without signals;
- forced first-rank FINISH/exit race;
- failed final receipt followed by idempotent cleanup;
- wrong reply sequence rejected;
- stop-pipe closure stops both ranks (coordinator death case);
- watcher fault during delayed native drain invokes the failure hook once and stops without signals;
- busy consumer slot cannot be overwritten.

All test subprocesses run at nice 19, idle I/O class, and OMP_NUM_THREADS=2. Temporary test directories are removed after the run. No hard kill or retry is used in cleanup. These tests exercise OS handover/failure behavior; native GPU draining and driver shutdown remain coordinator device-window gates.

## Window and canary follow-up

Two window-level findings were corrected: model-rank failure now invokes a failure hook to latch the boot marker before requesting stop/teardown, and the bounded drain loop continues polling the window watcher. The independent delayed-drain test exercises the latter. The coordinator exposes and records `--prompt-overlap off` for the matching sequential-prompt measurement. Final successful rank receipts require the matching rank identity and exactly one successful teardown; an empty teardown list cannot pass.

W0p creates one local Device per native process. Its CopyEngine and increment-operation borrowers leave scope before owner shutdown. Every increment uses the rank-local allocation and queue; local readback follows local drain. The coordinator checks both child PIDs alive for all 1,000 exchanges, validates shared bytes, and requires at least one overlap of native host command intervals. It explicitly does not compare unrelated device clocks or claim precise cross-card kernel overlap.

The optional owner stop channel checks pipe readability/closure at admission. It does not enter the shutdown release path, so a latched stop cannot prevent orderly drain and destruction. Fixture windows use the same cooperative pipe instead of signalling loading children. K0 cannot interrupt a currently executing JIT call; its bounded failure path retains and reports the process without a signal or hard kill.

The window wrapper checks the same-boot artifact/environment/card identities of prerequisite receipts, performs closed-environment and ldd preflights, checks visible foreign engine activity using read-only process fdinfo samples, and refuses a live boot fault latch. The foreign-activity check records the limit that private clients of other UIDs may be unreadable. W2 requires K0, K1a, K1b, K2 and W0p receipts; the new process model remains unqualified on devices until those coordinator windows pass.

## Native host failure gates

After the implementer confirmed the final GNU host binary, `fault_gates.py` launched two native host-only mini ranks for each of FAIL and STALL. Both cases passed: failed rank detected by EOF, stalled rank detected by the one-second command deadline, both peers stopped through the shared pipe, zero signals, no retained PIDs, one successful owner teardown per rank with zero live bytes and zero in-flight events. The failure-before-teardown receipt preceded the peer's final receipt.

`review-native-faults.json` retains the exact binary/test-source hashes, native receipts, ownership records and coordinator failure records. The ignored test directory was deleted after the evidence was collected. The native receipts explicitly report `device_executed=false`. No real GPU fault, stalled device drain, or driver teardown was exercised.

Final review coverage includes `pipeline.py`, `rank.hpp`, `rank_canary.hpp`, the optional owner stop-channel delta, fixture stop argument, and packet32's `window.py`. The canary/device windows remain prepared only. Source analysis and host fault injection do not establish native SYCL runtime behavior or simultaneous device execution.

## Final timing and command addendum

The final Python timing changes were reviewed without executing any device command. `decode_rank_metrics` clips each native host HALF interval to the same first-token through last-token completion span used for decode. Commands on each rank are serialized, so summing those clipped intervals does not double-count same-rank work. The receipt explicitly calls this native host HALF wall occupancy, including uploads/drains, rather than GPU busy time. Idle/coordination is the remainder of that span; per-interval values divide by the actual number of output intervals. Whole-request metrics remain separately labeled.

One final metadata inconsistency was found and fixed: class profiling had an empty speed field and diagnostic text but still carried `diagnostic=false`. Class mode now sets `diagnostic=true`, and the outer window receipt inherits that field. Scripted guesses and class profiling both leave `decode_tok_s` empty. The GNU host binary is now the CPU entry's default. No kernel, native ownership, or native arithmetic source changed during this follow-up.

All commands in `WINDOW.md` match the final window parser and prerequisite paths: K0, K1a, K1b, K2, W0p, W2s, W2n, W2d, W2c and the prompt-overlap-off W2s companion. K commands lower priority to nice19; W commands preserve the documented nice0 parent. The documented closed environment, adjacent-card argument, measured dispatch path, oracle path, output directories and receipt dependencies are consistent with the wrapper. These commands were read only, not run.
