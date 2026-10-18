# Packet118 lean orchestration

CPU preparation and evidence reading only. Nothing launches automatically.

Control is packet103's immutable bundle5 selection, decision
`1ad512f75aab3fce`. Candidate is bundle6 (`c9277d2c52987576`, fusion and repaired
target-head split) plus packet114's preregistered draft prefix **80,128**.
The prefix was selected from non-benchmark text; its size is never retuned from
benchmark prompts, outputs, acceptance or timing. Source decisions and the
prefix rule are copied into `inputs/`; no mutable parent readiness/output is
pinned. Exactly two new packet118 compositions are sealed.

The first handoff is `proposed-p118-smoke-B.txt`: twelve cold prompts × 64,
every token exact to `iq3-p49-split32-v1`, including the suffix-token regression.
The smoke is required before either composite can execute.

`proposed-p118-composite-A.txt` and `proposed-p118-composite-B.txt` each contain
control / candidate / control. Every prompt must be exact. The candidate must
beat the faster control by **at least 1.0% on each lane**. Different prefixes
may change draft acceptance; the two controls must agree, and fresh candidate
runs on A and B must agree on per-prompt acceptance counts. The full chain
retains its independent exactness and determinism gates. Identical selections
cannot establish a gain.

All proposals are tested on temporary queues. The registered chain directory
is fresh: `stage2/packet118-record-bundle/build/device-cards01-a`.
`ready.json` is false until all required evidence passes. `verify_ready.py`
rereads the actual receipts, policy seals, selection, launch-limit proof and
CPU-test receipt; a stored boolean alone is insufficient.

Use nice19, CPUs 8–15/24–31, Python `-B`, stdin `/dev/null` for CPU commands:

1. `prepare.py`: bind the fixed decision, chain metadata and proposed composites.
2. `launch_limit_gate.py`: intercept both actual rank launches for smoke,
   composite and chain. Its isolated negative child tests the old 8 GiB cap.
3. `orchestrate.py`: run the policy and submission CPU tests, retain their
   source-bound receipt, and write current readiness.
4. After both composites complete, `orchestrate.py --evidence-only` rereads
   evidence and updates readiness. No rebuild or test campaign remains.
5. The coordinator may use the command recorded in `ready.json` only when
   `verify_ready.py` passes. Preparation does not execute that command.

After a qualifying completed chain, `prepare_submission.py --chain <path>`
prepares the payload and portable evidence; `submission.py` provides the shared
submission CLI. Submission notes disclose the fixed non-benchmark prefix rule.
No submission occurs here. The inherited 128-token authorization remains
explicit; strict512 stays false. Fresh quality windows do not become pooled
performance repeats. Device imports never change resource limits.

[Work note](../../../../notes/2026-10-18-own-runtime-packet118.md).
