# Packet 76 — rank 1 host scheduling

Attribution completed on CPU from saved receipts. Of packet69's 1.608 ms
residual, 1.457 ms is host housekeeping outside its preparation, issue and wait
timers; 0.092 ms is outer setup; 0.001 ms is the observed device gap after the
last layer; 0.057 ms remains unresolved. The matched control has only 0.666 ms
in the housekeeping bucket. Observation overhead accounts for much of the
original residual. This is not a measured 1.608 ms opportunity.

The saved trace lacks per-submit timestamps, complete layer coverage and useful
copy timestamps. It cannot prove a complete causal split. The rank0 handover and
mailbox arrival precede the measured half. [Attribution and limits](../experiments/own-xpu-runtime/stage2/packet76-rank1-host/ATTRIBUTION.md),
[calculations and input hashes](../experiments/own-xpu-runtime/stage2/packet76-rank1-host/ATTRIBUTION.json).

The candidate is now sealed from copied packet70 sources. It retains the
selected wide64 experts, draft-HC and batch-copy setup. Rank1 can check the
terminal event on its ordered queue instead of polling every completed event
again. Synchronization, errors, release and teardown remain. New retirement
and profiling timers will show whether this addresses a useful part of the
host bucket. Kernels and arithmetic are unchanged.

Both engine builds pass. GNU and Intel each pass two fresh tiny mock runs:
3,072 output words match, with one completion query per drain instead of 768.
The full-shape allocation-only gate passes both selections at 23/25 and 24/24,
including the real post-load draft constructor and prepared target commands
after its allocations. No model arithmetic runs. All eight real memory-census
admissions pass; paired allocation censuses match byte for byte. All 76 Python
checks pass, including the shared lane-admission policy and worker import.

All six plans call the original pinned shared v4 wrapper. It admits new
lineages at 23/25, so every control and candidate uses 23/25; its actual 24/24
refusal is retained. No wrapper was copied or modified. Lane A runs fresh
production, candidate, fresh production. Lane B refuses unless A is entirely
exact and the candidate beats both controls, then repeats that sandwich.
Both proposed job files pass planning in a temporary queue. Nothing was added
to a live queue. The build is about 139 MB, below the 1 GB limit.

[Packet and commands](../experiments/own-xpu-runtime/stage2/packet76-rank1-host/README.md),
[final checks](../experiments/own-xpu-runtime/stage2/packet76-rank1-host/evidence/final-check.json),
[CPU closeout](../experiments/own-xpu-runtime/stage2/packet76-rank1-host/CPU-PREPARATION-CLOSEOUT.md).
The coordinator owns the next screens; device correctness and speed remain
unmeasured. The 1.61 ms is not promised savings.

No GPU, model, service, sudo or host-setting change. The initial pull was
blocked by a pre-existing dirty orchestration log; fetch proved local main
equal to origin/main. That log and all frozen paths were left untouched.
