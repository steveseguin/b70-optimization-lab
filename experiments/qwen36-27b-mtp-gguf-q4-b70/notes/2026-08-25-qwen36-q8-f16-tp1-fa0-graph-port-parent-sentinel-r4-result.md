# Qwen target-Q8/F16 TP1 fa0 graph-port parent sentinel R4 result

State: **PASS — mechanism and exact-output parity only**.

Both exact 64-token arms completed on the same rebuilt binary. Graph-off
reported every graph counter at zero. Graph-on completed 66 requests with four
miss/record/create events and 62 cache-hit/direct-replay events; all 66 requests
replayed. Rejection, unsupported, cache-full, update, and recreation counts were
zero.

Both arms produced exactly 1,290 bytes with SHA-256 `48c64a14...`. Process-group
cleanup, GPU idleness, model identity, packet identity, build identity, and the
34-library postflight closure all passed.

This closes the parent mechanism/parity gate that failed in R1 and R3. It does
not itself publish speed or authorize a record. The next step is to seal and run
the seven exact active-context graph cells against this same source and backend,
then apply the quality battery before website promotion. Protected graph-off
measurements remain immutable.
