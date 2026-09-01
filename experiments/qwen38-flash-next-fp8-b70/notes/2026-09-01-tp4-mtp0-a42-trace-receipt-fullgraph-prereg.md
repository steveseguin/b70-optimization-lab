# Qwen3.8 Flash-Next FP8 A42 trace-receipt full-graph preregistration

Date: 2026-09-01
Status: frozen before GPU launch

A42 is the fresh attempt-42/port-19714 successor to A41. It changes only fresh
paths/identity and the exact one-line pre-request diagnostic receipt proven by
the A41R static diff. The server, official FP8 revision, TP4/EP4 MTP0
placement, 4352-token limit, synchronous PLE, graph-safe oneCCL, full-decode
graph, trace, prompts, authorities, 16-repeat battery, three short rows, two
exact-4K rows, runtime verifier, teardown, and postflight remain unchanged.

The generator retains exact library-digest counts, rejects any 64-character
hash containing the new attempt identity, and requires exactly one stale
diagnostic receipt before replacing it with the disclosed `-torch-trace`
receipt. Any failure has zero quality or speed credit. A passing traced arm
still requires a trace-off repeat before promotion. No reboot or per-boot load
rule applies.
