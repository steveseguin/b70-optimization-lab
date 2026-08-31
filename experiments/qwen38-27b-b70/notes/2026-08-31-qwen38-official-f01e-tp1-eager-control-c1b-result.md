# Qwen3.8 official-f01e TP1 eager control C1b result

Date: 2026-08-31

Status: **failed exact control; 8/12 across fresh servers**

Both immutable-official-image arms passed the complete realistic workload,
cache-zero gate, objective canaries, direct model verification, cleanup, and
journal gate at 25.3340 and 25.0883 tok/s. Only 8/12 complete token arrays
matched. The mismatches were `benchmark-analysis`, `release-plan`,
`risk-register`, and `sql-debugging`.

Those are exactly the four prompts that differed in the current-image TP1
eager R9 repeat. Across the four R9/C1b servers, the other eight prompts were
exact and each failing prompt had two or three complete-output variants. The
official image uses Triton/FLA GDN while the current image uses native-XPU GDN,
so the shared failure set is evidence against the replaced GDN path and
against a regression unique to the current overlay. It is not proof that the
model is intrinsically nondeterministic: a shared numerical kernel can still
be repaired.

The next raw screen covers the other shared major stateful route: the exact
Qwen full-attention dimensions through paged FP16 KV insertion plus FA2
prefill and recurrent decode, at every actual strict-suite prompt length,
across fresh processes.

These rates are quarantined diagnostic measurements. No speed, quality, MTP,
or publication claim is authorized.

Structured result:
`../data/2026-08-31-qwen38-official-f01e-tp1-eager-control-c1b-result.json`.

Raw evidence remains under
`/mnt/fast-ai/bench-results/qwen38-official-f01e-tp1-eager-control-20260831-c1b`.
