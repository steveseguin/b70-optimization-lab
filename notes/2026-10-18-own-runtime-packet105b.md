# Packet105b / 106b: reset repair and suffix-heavy validation

CPU-only preparation, two-hour time box. No GPU, service, live queue, sudo or
host setting change is authorized. Builds use nice 19, CPUs 8–15/24–31,
closed stdin, an 8 GiB address-space cap and packet94's serial compiler turn.
The combined new build budget is 250 MB; frozen fixture inputs are linked.

The first `git pull --rebase` refused unrelated dirty orchestration files.
Fetch confirmed HEAD and origin/main both at `de42a7689`. Nothing was stashed,
reverted or staged from another task. All commits use explicit `--only` paths.

The new packet105b copies packet105 and restores rank0's private `active=1`
after importing the verified hidden state, before suffix submissions.
Packet106 already had that repair in both suffix services; packet106b copies
and preserves it. `copy-lineage.json` records the original source hashes.
Original packets, existing screens and existing ops files remain frozen.

Only scheduled views are gated: production and compute head split in 105b;
production, head split and combined head/draft split in 106b. BCS and draft-only
are outside this request. Every selected composition requires all 11 startup
windows, with an individual receipt written immediately after each window.

Implementation and CPU gates are in progress. Device results remain pending.
The first deliverables will be new microbenchmark and 12-prompt/64-token smoke
proposals, planned on temporary queue copies. No proposal is a device pass.
