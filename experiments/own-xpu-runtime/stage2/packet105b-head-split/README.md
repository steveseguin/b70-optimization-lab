# Packet105b: reset repair and suffix-heavy validation

New copy of frozen packet105. The only production runtime delta is the private
rank0 `active=1` upload before suffix submissions, after the verified hidden
import. Packet105x proved why request reset otherwise skips the suffix argmax.
No weight, logit arithmetic, merge tie rule, KV precision or speculative state
changes. The original packet and all old evidence remain frozen.

CPU gates pass: GNU/Intel exact logit and winner bytes in two fresh processes
each, old-failure/new-fix regression (21 cases per process), controller and
loader/transfer mocks, four rank allocation checks, and all eleven startup
windows for production and compute head split (22 total). Only these views
will run. BCS is outside this task. Each completed window has an immediate
source-bound receipt under `build/startup97e/receipts/`, retained in the evidence
archive. A rerun reuses matching receipts; changed inputs invalidate them.

The device micro compiles but has NOT run. It uses the exact production head,
argmax and pack kernels on synthetic expanded Q6 weights and 4,096 hidden
vectors. Scaling sentinel coordinates forces suffix winners. It requires at
least 2,000 suffix winners, 256 boundary ties, 768 NaN/+Inf/-Inf row cases,
256 batch resets, one detected old-bug negative control and zero repaired
mismatches. Full logit bytes and finite winner payloads must agree; invalid
rows must refuse token publication. This is a diagnostic operator test, not a
model performance measurement or a model quality pass. It uses one B-lane card;
the full model smoke tests the actual two-rank path.

The new proposed files are under `../../ops/lane-queue/`:

1. `proposed-p105b-micro-B.txt`: coordinator-owned device diagnostic.
2. `proposed-p105b-smoke-B.txt`: candidate only, all twelve prompts, 64 tokens
   each, reset before every request. Execution refuses until the micro passes.
   Every token must match the oracle, including architecture-tradeoff token31
   (215495), and a suffix winner must be observed. No warmup prompt is run.

Both proposals pass the real planner on temporary queues. Neither is installed
in a live queue. The model smoke is capped screening evidence, never a final
realistic-suite headline. Device equality, repeats and speed remain pending.
The combined grid and conditional A confirmation live in [packet106b](../packet106b-draft-split/README.md).

CPU commands run from the repository root using
`nice -n 19 taskset -c 8-15,24-31 python3 -B <packet/script.py> </dev/null`.
Scripts impose an 8 GiB address-space cap and serialize compilation through
packet94's compiler turn. Run `build_engine.py`, `reset_regression.py`, then
`cpu_milestone.py cpu_gate.py controller_gate.py full_shape.py runtime_mock.py
startup97e.py`. `prepare_packet.py` creates seals only in new unsealed views;
it refuses to replace them. `build_microbench.py`, `propose_micro.py` and
`propose_smoke.py` compile/plan only. Read the [retention instructions](RETENTION.md)
before restoring local build inputs. Remaining copied preparation scripts are
historical parent utilities, not an alternative launch path for this packet.

[CPU closeout](closeout.md) · [work note](../../../../notes/2026-10-18-own-runtime-packet105b.md)
