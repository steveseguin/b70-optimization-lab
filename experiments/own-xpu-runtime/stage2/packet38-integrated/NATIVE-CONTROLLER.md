# Native request controller

The Python wrapper starts the same two rank processes, prepares a shared mapping,
and sends command 10 to each rank once per request. Rank 0 runs the scheduling
state machine and its own model half. Rank 1 executes a single-command mailbox.
The wrapper waits on request completion while checking its watchdog, stop pipe,
child ownership and journal cursor; it performs no per-token socket handovers.
Command 0 ends the native worker for that request; the ranks then return to their
socket loop for request reset or graceful finish. Python remains the reference.

The mailbox lives at `2 * 65536 + 256` in the existing mapping. An aligned 32-bit
request sequence publishes the command with release ordering; rank 1 acquires
that sequence before reading it. The reply uses a separate release/acquire
sequence. A producer cannot overwrite an outstanding slot. Request completion
is a predicate, not a wakeup: futex EAGAIN is handled by checking it again.
There is no spin. Futex sleep is at most 10 ms per cancellation check and every
operation has an absolute deadline. A failure publishes the shared abort word
and wakes both sequence addresses before propagating into receipt/teardown.
No failed operation is retried. Independent review is retained in
`review-resume-controller.md`.

Rank 1 only computes confirmed tokens. A guess can start rank 0's next half,
but only the unchanged rank-1 target reply is emitted. A hit accepts that
candidate; a miss restores recurrent banks and token history then redoes the
half with the verified token. Draft publication must match valid/error flags,
position, sequence and vocabulary bounds; an invalid publication suppresses
guessing. End-of-generation discards an outstanding speculative candidate.

`native_controller_gate.py` compares 1,123 CPU state-machine cases against the
Python Controller: all 1,093 ternary hit/miss/no-guess scripts of lengths 0–6,
24 long random scripts, and six reference-mode/overlap/end cases. It compares
tokens, the complete guess and hit/miss sequences, counters, final state and
fixtures. `native_mini_gate.py` additionally runs the actual host Engine through
both controllers using the same ranks and complete request resets. The final
resident/prepared host binary passed 1,109 cases: the same 1,093 exhaustive
patterns, twelve random 64-token requests, and four mode/end cases. It compares
every target allocation and alternate bank, retained fixture, draft final state,
emitted token, guess and hit/miss event. `native-mini-cpu.json` binds this proof
to the final binary SHA256; its 399.001-second wall time is test duration only.

The retained ordinary CPU microbenchmark measured 11.04 microseconds median
between one half finishing and the other half starting (p95 17.78 us), and
4.11 us median mailbox send-to-worker start. This is a tiny CPU model with no
GPU work; it predicts no model throughput. Exact receipt values are in
`native-controller-cpu.json`. Zero spin iterations were used.

AddressSanitizer, UndefinedBehaviorSanitizer, and ThreadSanitizer passed all
1,123 cases and all five fault/lifecycle gates. GCC 13's ThreadSanitizer runtime
failed before main with an unexpected memory mapping; the CPU-only Intel LLVM
22 runtime runs successfully. No host setting was changed, and the LLVM test
binary is compiled without SYCL. `native-controller-tsan-gcc13.json` preserves
the failed runtime attempts; `native-controller-tsan.json` is the completed
TSan gate. `native-build-receipt.json` records binary hashes and compile/link
precision flags.

The current scheduler runs rank 0's HALF synchronously in rank 0's main thread
while rank 1 works independently. This preserves emitted tokens, guesses,
rollback and final state, but may delay rank-1 ACCEPT and the next draft until
rank 0 finishes a slower half. Python can process the earlier rank-1 reply
while rank 0 is still busy. Thus the native controller does not yet reproduce
all of Python's possible draft overlap. This is an explicit pending performance
limitation, not evidence of a speedup. Adding a local scheduling thread would
need a new bounded lifetime design and qualification.

`native-mailbox-faults.json` retains five bounded CPU fault/lifecycle gates:
a missing peer times out, a worker exception wakes its scheduler, cancellation
interrupts a sleeping waiter, and 32 successive requests reuse and terminate
the same mailbox without stale payloads, and a queued command cannot start
after its peer has published abort. The final check covers both remote worker
admission and local rank admission.
