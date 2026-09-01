# Qwen3.8 Flash-Next FP8 A41 authority-safe full-graph preregistration

Date: 2026-09-01
Status: frozen before GPU launch

A41 is the fresh attempt-41/port-19713 successor to the pre-load A40
interruption. It preserves A40's model, revision, runtime, TP4/EP4 MTP0
placement, 4352-token limit, 128 MiB KV allocation, synchronous 12 GiB/rank
PLE, full-decode-only size-1 graph configuration, trace, sampling, prompt
order, exact output authorities, complete quality battery, teardown, and
postflight behavior.

The only substantive generator repair is authority protection:

- the accepted exact-depth request-payload SHA-256 is restored once in the
  generated client;
- the exact pinned oneCCL digest must remain present 3/3/2 times in generated
  launcher/client/supervisor source;
- after repair, no 64-character hexadecimal token may contain the new `a41`
  attempt identity;
- all counts and final generated sources are hash-bound and fail closed.

Any failure remains a bounded negative. A speed observation is not promotable
unless the unchanged quality and authority battery passes. Because the causal
trace remains enabled, even a passing result requires a fresh trace-off repeat
before promotion. Existing `5.515783 tok/s` MTP0 and `20.727176 tok/s` MTP4
results remain protected. No reboot or one-load-per-boot rule applies.
