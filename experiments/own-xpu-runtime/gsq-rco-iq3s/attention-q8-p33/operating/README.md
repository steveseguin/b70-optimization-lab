# Candidate resident correctness run preparation

This adapter is source preparation only; root owns physical admission and launch.
The [materialization recipe](prepare.py) verifies the frozen serving adapter and
all-12 baseline suite, then writes explicit private copies and an
[exact patch](overlay.patch). Original sources remain unchanged. The candidate
adapter selects `../evidence/native-build.json`, the expanded-Q8 memory ledger,
and adds `--attention-q8-p33`; native protocol, RESET, fault and cleanup code stay
inherited. There is no Host or alternate model override.

The run uses one persistent pair with the original two disjoint eight-token
warmups and twelve fixed prompt pairs, alternating target/MTP order. Every request
starts with a full RESET. Each measured arm first retains its token/state evidence,
then must exactly match the corresponding arm of the independently audited
baseline before another request is allowed. Prompt00 target-only is the first
measured gate; failure prevents its MTP counterpart. The same owners continue
through the remaining cases only after each gate passes. Early EOS remains part
of the comparison. No rollback, retry, reload, or hard kill is added.

The [coordinator](once.py) imports the exact frozen baseline `run()` and first-run
Monitor into private modules. It binds the candidate suite/class, fixed new output
paths and unit, and increases initial available RAM by 94,371,840 bytes. Rank
logical device forecasts increase by 47,185,920 bytes each; full physical admission
still applies. State forecast remains 27 dumps (initial blank plus 26 requests),
6,316,056,364 bytes including metadata allowance, with 2 GiB external reserve and
27 GB root floor plus 128 MiB cache allowance. No evidence is pruned.

`python once.py --plan` requires root-created private control parent,
completed candidate native/CPU proof and the authenticated actual48 finite-scale census,
source-bound independent operating review,
and immutable independently audited baseline evidence. It performs no device
operations. `--run PLAN` is reserved for root's later reviewed safe unit admission;
all inherited monitor checks apply. The fixed unit is
`gsq-attention-p33-a.service`, control is
`/home/steve/own-xpu-runtime-results/gsq-attention-p33-a.control`, and retained state
is `/mnt/usb-models/own-xpu-runtime-results/gsq-attention-p33-a`.

Timings are descriptive. Comparing this separate process with the earlier
baseline is not a speed promotion or a record claim. Exactness is same-engine
baseline token/target-state equality, not independent model quality validation.
