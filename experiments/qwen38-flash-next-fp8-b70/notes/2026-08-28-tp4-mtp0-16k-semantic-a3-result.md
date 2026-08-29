# Qwen3.8 Flash-Next FP8 TP4 MTP0 active-16K semantic A3 result

Date: 2026-08-28
Status: Phase 1 quarantined; Phase 2 correctly blocked

The first request on attempt 3 passed the natural 16K retrieval oracle. It
used 16,213 prompt tokens, returned all five exact JSON fields in 62 completion
tokens, exposed a complete token-id stream, and reported zero cached tokens.
TTFT was 954.794432 seconds and the natural-completion rate after first text
was 5.439150 tok/s. That rate is diagnostic only; it does not replace or lower
the protected 5.219484 tok/s structural observation.

The identical second request on the same server completed but was corrupted.
It again reported 16,213 prompt tokens and zero cached tokens, yet returned 128
repetitions of `duct`, failed every semantic field, and ended at the output cap.
Its TTFT was only 81.991736 seconds and its diagnostic rate was 5.621500 tok/s.
Prompt hashes matched, while text and token-id hashes differed. The sharp
prefill reduction plus wrong repeated output is scoped evidence of reused or
stale long-context runtime state that is not represented by the API cache
counter. It is not evidence of a model-weight or first-request failure.

The client exited nonzero before writing a pass adjudication. The supervisor
performed controlled teardown and left no server, listener, compile path, RPC
path, or high-memory card. All four cards returned below 42.89 MiB and the
journal contained no B70 reset/fatal event. It did retain six corrected APEI
records and seven local-NVMe receiver lines despite the model being read from
the external volume, proving that this host-level storage-link caveat is not
eliminated merely by moving checkpoint reads.

The fresh-server Phase 2 was correctly blocked by the frozen dependency on a
Phase-1 pass. This cell remains Grade-D quarantined, now with a concrete
same-server semantic failure rather than an absent repeat gate. A separately
registered fresh-server-only successor may compare one new first request with
the correct request-1 hashes; it cannot erase the repeated-serving failure.
Deeper 24K/32K serving remains blocked until the repeated-state mechanism is
fixed or explicitly isolated.

The 70-entry external manifest verifies and has SHA-256
`03be182441d7e23a6b49bc02303628347b81fa46a22c1c41e145adb9cac949b0`.
No protected speed, quality, deployment, or featured result changed.
