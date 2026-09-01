# Qwen3.8 Flash-Next FP8 A40 payload-authority interruption

Date: 2026-09-01
Status: preserved pre-load interruption; no inference evidence

A40 passed preflight and issued the server command. A concurrent independent
static audit then found that the broad `a39` to `a40` identity replacement had
also altered the inherited exact-depth request-payload authority SHA-256. The
generated client expected a digest containing `e2a400032`; the accepted anchor
authority contains `e2a360032`.

The supervisor was interrupted immediately. The server log remained empty, no
model worker or checkpoint load was observed, the endpoint never became
healthy, and zero inference requests were sent. Teardown left no matching
process or listener; all four devices remained visible with idle memory. A40
has no quality or speed credit and protected results are unchanged.

A41 is a fresh attempt/port successor. In addition to exact count checks for
the pinned oneCCL digest, its generator restores the one exact-depth payload
authority occurrence and rejects any 64-character hexadecimal token still
containing the new `a41` identity after generation. This catches unknown future
attempt-name collisions rather than maintaining an open-ended exception list.
