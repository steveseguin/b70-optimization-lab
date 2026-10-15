# Packet45 fix 6: small GEMV plan eligibility closeout

## Root cause

Both measured device dispatches reproduce the same CPU exception before any backend or model payload is used: `small.ffn`, first member `blk.24.router`, follower `blk.24.shexpup`. The follower exists, is still labelled `gemv`, and is on the same card, but **its inputs differ**. P39's selected shared-up activation epilogue already added the gate-activation dependency to that launch. It is no longer a member of the original primitive GEMV tuple. KD constructs target rank1 with the capture path's fixed 24/24 split for either draft placement, so the first failing label is the same on both pairs.

This is a composition failure between independently exact fusions. It is not a missing allocation, a card failure, or a mismatch in the model's arithmetic. K2 measured each candidate successfully but the former CPU plans used the static dispatch with small tuples disabled; they did not exercise this measured combination.

## Repair and strict checks

The small-group constructor now resolves all labels, retaining duplicate detection. If any member is absent or already rewritten by a registered P39 epilogue, it leaves the existing plan schedule alone. It installs no small-group/follower entries for that group. Complete primitive tuples still require the original operation, card, input, ordering, output and arithmetic-tuple checks. Existing P39 fusions keep their selected execution; the remaining GEMVs execute through the ordinary exact path. No numerical kernel, allocation, owner guard or ABI changes.

Nine metadata-only checks pass: complete groups still fuse (83 in the test plan); an absent follower skips only that group; wrong card, different input, wrong operation, duplicate label, wrong shape, overwritten input and early output use are rejected.

## Plan sweep

The helper extracts the actual `plan`, `pipeline::split`, `selected_variant`, Engine grouping body and draft-plan construction from the production sources. It reads only `build/input/plan.tsv`; it has no backend and performs no tensor arithmetic or weight reads. Both measured dispatches are copied byte-for-byte from the incident. The forced dispatch enables every fusion key, with the registry-required matching GEMV/class choices. Two preliminary forced configurations were correctly rejected by the registry (route dependency, then HC low choice); their inputs and refusal evidence are retained.

All **48 plan × dispatch rows pass**. Target rank0/rank1 cover both 22/26 and 24/24 placements; contexts are 4096 and 32768. KD capture and the actual draft plan are also constructed for both placements. The draft constructor has its own unfused dispatcher and does not call Engine's small-group builder; its real paired-expert schedule check is exercised. W2m, WS, WS128x and WS128 share these target/draft constructors; WSs uses the target constructors without the draft.

| Plan | Context | Draft rank | Execution rank | Dispatch | Groups | Launches | Result |
|---|---:|---:|---:|---|---:|---:|---|
| target | 4096 | 0 | 0 | dr0 | 17 | 664 | pass |
| target | 4096 | 0 | 1 | dr0 | 19 | 776 | pass |
| KD | 4096 | 0 | 1 | dr0 | 18 | 716 | pass |
| draft | 4096 | 0 | 0 | dr0 | 0 | 48 | pass |
| target | 4096 | 1 | 0 | dr0 | 18 | 724 | pass |
| target | 4096 | 1 | 1 | dr0 | 18 | 716 | pass |
| KD | 4096 | 1 | 1 | dr0 | 18 | 716 | pass |
| draft | 4096 | 1 | 1 | dr0 | 0 | 48 | pass |
| target | 32768 | 0 | 0 | dr0 | 17 | 664 | pass |
| target | 32768 | 0 | 1 | dr0 | 19 | 776 | pass |
| KD | 32768 | 0 | 1 | dr0 | 18 | 716 | pass |
| draft | 32768 | 0 | 0 | dr0 | 0 | 48 | pass |
| target | 32768 | 1 | 0 | dr0 | 18 | 724 | pass |
| target | 32768 | 1 | 1 | dr0 | 18 | 716 | pass |
| KD | 32768 | 1 | 1 | dr0 | 18 | 716 | pass |
| draft | 32768 | 1 | 1 | dr0 | 0 | 48 | pass |
| target | 4096 | 0 | 0 | dr1 | 17 | 664 | pass |
| target | 4096 | 0 | 1 | dr1 | 19 | 776 | pass |
| KD | 4096 | 0 | 1 | dr1 | 18 | 716 | pass |
| draft | 4096 | 0 | 0 | dr1 | 0 | 48 | pass |
| target | 4096 | 1 | 0 | dr1 | 18 | 724 | pass |
| target | 4096 | 1 | 1 | dr1 | 18 | 716 | pass |
| KD | 4096 | 1 | 1 | dr1 | 18 | 716 | pass |
| draft | 4096 | 1 | 1 | dr1 | 0 | 48 | pass |
| target | 32768 | 0 | 0 | dr1 | 17 | 664 | pass |
| target | 32768 | 0 | 1 | dr1 | 19 | 776 | pass |
| KD | 32768 | 0 | 1 | dr1 | 18 | 716 | pass |
| draft | 32768 | 0 | 0 | dr1 | 0 | 48 | pass |
| target | 32768 | 1 | 0 | dr1 | 18 | 724 | pass |
| target | 32768 | 1 | 1 | dr1 | 18 | 716 | pass |
| KD | 32768 | 1 | 1 | dr1 | 18 | 716 | pass |
| draft | 32768 | 1 | 1 | dr1 | 0 | 48 | pass |
| target | 4096 | 0 | 0 | forced | 17 | 618 | pass |
| target | 4096 | 0 | 1 | forced | 19 | 724 | pass |
| KD | 4096 | 0 | 1 | forced | 18 | 668 | pass |
| draft | 4096 | 0 | 0 | forced | 0 | 48 | pass |
| target | 4096 | 1 | 0 | forced | 18 | 674 | pass |
| target | 4096 | 1 | 1 | forced | 18 | 668 | pass |
| KD | 4096 | 1 | 1 | forced | 18 | 668 | pass |
| draft | 4096 | 1 | 1 | forced | 0 | 48 | pass |
| target | 32768 | 0 | 0 | forced | 17 | 618 | pass |
| target | 32768 | 0 | 1 | forced | 19 | 724 | pass |
| KD | 32768 | 0 | 1 | forced | 18 | 668 | pass |
| draft | 32768 | 0 | 0 | forced | 0 | 48 | pass |
| target | 32768 | 1 | 0 | forced | 18 | 674 | pass |
| target | 32768 | 1 | 1 | forced | 18 | 668 | pass |
| KD | 32768 | 1 | 1 | forced | 18 | 668 | pass |
| draft | 32768 | 1 | 1 | forced | 0 | 48 | pass |

## Evidence and qualification

`fix6-plan-gates.json` binds the source, measured/forced dispatches, reproduction, 48-row sweep and nine mutation checks. `evidence/fix6/before-seal.jsonl.gz` retains the preceding seal and receipts; the exact original main source is retained for before/after reproduction. Incident files remain read-only.

Only the GNU host and device binaries that link the changed main entry were rebuilt (GNU 74.82 seconds; device 162.01 seconds). Other modes and the previous qualification evidence are retained. The prior compiler objects had been deleted, so their link dependencies must be reconstructed; unaffected standalone owner tests are excluded from the build targets.

Qualification decision pending: `seal_context.py:83` requires the current compiled-source closure for all modes, including ASAN (previous rebuild 220 seconds). `fixture_delta.py:27` rejects changes outside the prior two fixture files. Per the owner's explicit stop rule, no ASAN build or real-model suite has been started; the requested evidence-reuse decision is pending. Do not claim a new qualifying seal yet.

All five device executable hashes changed; ABI and numerical kernels are unchanged. All 41 artifact hashes and ten protected incident hashes verify. `evidence/fix6/handoff.json` records the current binaries and the uncompleted qualifying-seal status. The existing diagnostic-unsealed mode can admit these actual hashes, but no new qualifying seal is claimed.
