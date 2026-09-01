# Qwen3.8 Flash-Next FP8 A37 attempt-binding negative

Date: 2026-09-01
Status: preserved pre-load procedural negative

A37's supervisor and client correctly used attempt 37/port 19709, but its
generated launcher retained `ATTEMPT=36`. The launcher therefore refused to
overwrite A36's preserved evidence before creating a model server or loading a
checkpoint. Zero inference requests were sent. Postflight found no B70 journal
event and 42.875--42.883 MiB used per card.

A38 is a fresh path-only successor. Its derivation explicitly changes the
inner launch attempt to 38 in addition to the supervisor/client/run/cache/RPC
paths and port 19710. The trace policy, verifier, model, graph, performance,
quality, and teardown identities are unchanged.
