# Qwen3.8 27B Q4_K_M TP1 HTTP concurrency r2

Status: **failed strict identity; retained pilot for r3**.

Two fresh cache-off servers agreed within 1.62% at every 1→64-user point.
The median aggregate curve is `25.12, 37.66, 50.30, 57.57, 55.59, 65.97,
84.39 tok/s`. Each request returned the full 128 raw token IDs. Attempt 5
reported zero reused prompt tokens for all 191 oracle and batch requests;
attempt 4 used the same hard-disabled server cache configuration and fully
evaluated prompts, but its older adapter mistakenly stored live slot length
as the cache field. No generated token sequence matched an oracle belonging
to a different base task.

This did not pass r2's preregistered gate. Greedy token identity matched the
per-prompt sequential oracle for every request at one and two users, then
became batch-shape-dependent above two. That behavior remained after prompt
caching and slot similarity were disabled. The curve is suitable for showing
measured HTTP capacity with an explicit output-variation warning; it must not
be described as bit-exact or batch-invariant. The output-isolation rule was a
post-hoc observation here, then frozen before the separate r3 confirmation.

The earlier r1 OpenAI-compatible attempt had two measurement defects: it
could not return raw IDs, and its second ascending pass reused a long-lived
server whose midpoints collapsed by 40–72%. R2 uses llama.cpp's native HTTP
endpoint for raw IDs and restarts the server between retained attempts. Two
intermediate r2 attempts exposed the endpoint and cache-field adapter issues;
they remain failed diagnostics and are not averaged into the curve.

See the [compact result](../data/2026-08-25-qwen38-q4km-tp1-http-concurrency-r2-result.json),
[preregistration](../data/2026-08-25-qwen38-q4km-tp1-http-concurrency-r2-prereg.json),
and [runner](../scripts/run-qwen38-q4km-tp1-http-concurrency-r2.sh).
The package curve comes from r3, not these pilot values.
