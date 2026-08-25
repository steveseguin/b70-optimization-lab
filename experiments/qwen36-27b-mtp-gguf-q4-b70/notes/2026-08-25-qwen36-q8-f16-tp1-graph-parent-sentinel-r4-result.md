# Qwen3.6 target-Q8 F16 TP1 graph parent sentinel R4 result

State: **failed-incomplete only because live origin advanced after both arms**.

R4 passed model verification, GPU compute, the graph-off control, the graph-on
candidate, exact output parity, cleanup, and every graph gate. The candidate
recorded four graphs and served 62 direct cache replays across 66 requests,
with zero compatibility/device rejection and cache limit 8. Both raw stdout
files have SHA `cc12d7e...`.

Before the final postflight completed, unrelated commit `b8858afac` advanced
live `origin/main` with Qwen3.8 HTTP concurrency and clean-host publication
work. R4's local launch HEAD, packet blobs, model, binary, and runtime did not
change. The frozen live-remote equality rule still failed the campaign, so R4
authorizes no expansion and no arm reuse.

R5 preserves live-origin equality as a mandatory prelaunch gate. After launch,
it freezes and rechecks the local launch HEAD, exact packet Git blobs, model
stat, binary/build/protected hashes, 34 DSOs, cleanup, and idle state, but an
unrelated later remote commit cannot invalidate completed immutable work.
