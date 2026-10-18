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

The suffix microbenchmark compiles and its new proposal passes the real queue
planner on a temporary queue. It runs 4,096 hidden vectors with full-vocabulary
production Q6 head and argmax kernels. At least 2,000 must have suffix winners;
256 cases have exact cross-boundary ties, 768 inject NaN/+Inf/-Inf rows, and
256 batch resets clear the private controls. A negative control must detect
the old skipped-suffix bug. Both complete logit bytes and finite winner payloads
must match; nonfinite rows must refuse output. Synthetic weights make these
stress cases reproducible: this is device operator validation, not a model
speed or quality claim. Device execution remains pending.

First deliverable: `ops/lane-queue/proposed-p105b-micro-B.txt`, under the
own-runtime experiment. Only the coordinator may execute it. Its existing
supervisor retains lane admission, fault review, memory/FD monitoring, graceful
stop and drain. No live queue was installed.

Both host and device binaries compile for 105b. GNU and Intel each pass two
fresh full-vocabulary byte checks and the reset regression (21 cases per run,
six old-code failures). Controller and actual-runtime loader/transfer mocks
pass. Startup found a frozen fixture copy without execute permission; the new
packet now links byte-identical executable frozen inputs, leaving both parents
unchanged. Every-window startup and the 12-prompt smoke proposal are next.
