# Packet97: compose the in-flight exact choices

The new bundle copies packet91 and adds the packed target head, reply-first
reporting, HC norm fusion, expert grid prefetch and exact half-scale cache.
Grid prefetch and the half-cache compose in one kernel. H1 remains closed.
The recorded frontier is still packet84's 55.68696298163401 tok/s; this work
contains no new device result.

The GNU and Intel builds pass. Each compiler passes two fresh byte repeats for
every changed operator, including the combined expert path and reply-first
state/error cases. The 128 selectable compositions bind those raw operator
transcripts. All 256 full-size startup checks pass, including actual allocation
and VRAM admission on both ranks, with model payloads/backend mocked only.
The packed target head's separate expanded draft prefix is included.

The compiled composition and CPU proof were committed and pushed as
`3566f04a0`. All 128 selections are now sealed. The largest composition and the
restored baseline both pass the complete CPU chain rehearsal, including window
plans and submission consumers. The packet tests pass 276 tests and 136
subtests; orchestration passes 29 tests. Both lane proposals pass planning on
temporary queue copies: six control/candidate/control jobs in total.

The orchestrator reads both directions through each source compare module.
The final snapshot rejects packet91's A screen with the source comparator's
`unfinished/failed screen` verdict; its B grid and the other five sources remain
pending. Readiness is false. The full-chain disk check also remains false:
15,752,671,232 bytes free versus 18,812,225,206 required, a 3.06 GB shortfall.
The CPU build uses 334,579,274 bytes. No storage reserve was lowered and no
unrelated evidence was deleted. A fresh invocation rechecks current evidence.

Tests cover invalid evidence, revert-only pins, closures, both comparison
directions and the packet84 temporary-path regression. The submission tool
already passes the frozen receipt bytes as `data=` and discloses the packed
target head's separate expanded draft prefix. These tools were finalized before
the final seals. No GPU, service, live queue, frozen tree or host setting was
changed by this work.

Commands and evidence are under
`experiments/own-xpu-runtime/stage2/packet97-record-bundle/evidence/`.
Build commands use nice 19, cores 8–15/24–31, stdin /dev/null, the packet94 compile
turn guard and an 8 GiB address-space cap. Root remains above 12 GB free; build
scratch is well below 1.5 GB. Each fixture scratch directory is removed after its
verified raw transcript and case log are archived.

The largest composition leaves 4,225,394,604 bytes of arena headroom on rank0
and 639,463,734 on rank1. Rank1's planned free VRAM is 2,669,506,870 bytes,
above the unchanged 1.5 GB floor. The minimum arena headroom across every
selection is 630,519,094 bytes on rank1 (half-cache without the packed head).
These are allocation/admission checks, not measured device memory use.

Final receipts: [CPU verification](../experiments/own-xpu-runtime/stage2/packet97-record-bundle/evidence/final-verification.json),
[closeout](../experiments/own-xpu-runtime/stage2/packet97-record-bundle/CPU-PREPARATION-CLOSEOUT.md),
[orchestration instructions](../experiments/own-xpu-runtime/ops/packet97-orchestration/README.md).
Proposals: [lane A](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p97-A.txt)
and [lane B](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p97-B.txt).
The current templates refuse execution. Once source decisions resolve, the
helper writes the confirmed selection and fresh output paths, then plans the
actual jobs. Full-model oracle equality, device determinism and speed remain
future gates; the CPU byte evidence is a factorized operator proof.

The requested initial `git pull --rebase` refused unrelated dirty work. A fetch
showed main equal to origin/main; no unrelated file was stashed or overwritten.
A read-only subagent reviewed orchestration while the existing GPU job ran,
as AGENTS.md directs. All implementation and compilation remained serial here.

## Packet97b — review 14: screen the composite first

The owner changed composition admission: one exact first-lane win qualifies a
source. The new adapter retains the source's sealed loader/chooser, 13/13 exact
checks, chronological same-lane controls, current boot and unchanged per-prompt
acceptance. It no longer waits for that source's second lane. Pending sources
are left out of the decision instead of delaying the whole composite. The
composite itself must pass control/composite/control on both lanes. No source
or microbenchmark gains are added together: packet93's roughly 47% transfer
from its head microbenchmark to its engine step is the reason to measure the
whole combination.

The decision used here contains packet91's route-fast plus rec-both-plus,
packet93's head-transpose and packet90's E1 half-cache. Packets92 and 94 are
pending in the final snapshot. Packet95 finished during this work: its E3 path
was exact but lost on B (55.235207 versus 55.479524 / 55.495027), so it has no
qualifying win and is excluded. E1 remains a composition option, not a reopened
standalone claim. The measured source rows are:

| Source | First lane | Candidate tok/s | Opening / closing control tok/s | Gain over stronger control |
| --- | --- | ---: | ---: | ---: |
| 91 route + recurrence | A | 55.743640 | 55.386160 / 55.390176 | +0.6381% |
| 93 head transpose | B | 55.928454 | 55.396357 / 55.510063 | +0.7537% |
| 90 half-cache | B | 55.656613 | 55.516521 / 55.488676 | +0.2523% |

Every source bracket passes all thirteen exact checks and preserves per-prompt
acceptance. These are source screens, not a packet97 composite measurement or a
record. The baseline for the new composite is the unchanged packet84 selection;
packet91's route/recurrence join the candidate rather than being silently
included in its control. This makes the whole-source comparison meaningful.

### Why packet91 was called rejected

The saved base at `6d434dbac` says `source 91 invalid: unfinished/failed screen`.
Its accepted window hashes cover A-grid indices 0, 1 and 2; the next window was
the combined candidate at index 3. The source comparator emits that same error
for an unfinished window and a failed one, before checking the lane/selection
identity. The old adapter converted that generic error into `failed`.

At the first packet97b recheck, windows 0–3 had passed and the closing control
`p91-A-grid-4-control/window.json` had `passed=false`, no `finished_utc_ns`, no
stop reasons and no retained child. That is incomplete evidence, not an
identity or quality rejection. It subsequently completed: the closing control
is 55.390176 tok/s, and the combined candidate beats both controls exactly.
The earlier in-progress receipt bytes have since been replaced by their final
receipts; the base snapshot identifies where its read stopped, not a preserved
failure receipt. Current source identity checks pass unchanged.

The adapter now labels an unfinished window **pending**. Stop reasons, retained
children, report failures, completed invalid windows and missing artifacts from
finished windows remain failures. No source comparator or other packet tree
was edited to obtain the pass.

### Proposals, fallback and record boundary

The generator writes
`experiments/own-xpu-runtime/ops/lane-queue/proposed-p97-composite-{A,B}.txt`.
Each lane gets control/composite/control using existing packet97 sealed views.
The decision includes the qualified source evidence and tool hashes; job
arguments bind its file hash, and every output path includes its identity.
`composite-plans.json` points to the final decision. Use `orchestrate.py
--decision <that-file>` to evaluate the same set after its screens finish,
without picking up sources that qualified later. Started brackets are read
without trying to plan their occupied output paths again.

If the smaller composite lane gain is below the best selected single-source
gain, or below +0.5%, readiness remains false and leave-one-out jobs are emitted.
The comparison uses gain over the stronger same-lane control, never absolute
cross-lane speeds or added standalone wins. Equality at either threshold does
not trigger fallback. The generator also handles an exact composite that loses.
For this decision, each lane's gain must reach +0.7537% to avoid fallback.

`composite_jobs.py --decision <that-file> --leave-one-out` creates the conditional
`proposed-p97-leave-one-out-{A,B}.txt` files from the already sealed 128 views.
It removes one source per bracket: packet91's winning arm together, head
transpose, or half-cache. E1/E3 removal preserves the other expert feature when
both are present. Each view gets its own control/view/control on both lanes.
These proposals do not claim the fallback has been triggered by a measurement.

`--pin` remains baseline-only; `--closed` still requires a reason and explicit
baseline pins for all affected dimensions, and cannot hide failed evidence.
A partial packet91 pin removes its whole qualified arm. The new
`composition_ready` field is separate from `ready`: source qualification permits
screens, while record readiness still requires the composite's two exact
winning brackets, the existing chain-admission rule, and the full sealed chain,
CPU rehearsal, storage and input checks. The frozen record chain is unchanged.

### CPU validation and scope

The orchestration suite passes **52 tests** with
`/home/steve/.venvs/deepseek-v4-xpu/bin/python -B -m pytest`; the existing
packet97 and lane-admission suites pass **59 tests**. All use nice 19, cores
8–15/24–31, no pytest cache, and stdin `/dev/null`. The tests cover single-lane
admission, unfinished versus failed receipts, pin/closure rules, candidate
binding, immutable decisions, two-lane composite exactness and acceptance,
threshold boundaries, losing composites, expert-preserving leave-one-out
views, occupied-output resume and temporary queue isolation. Read-only review
found two issues (partial-pin verification order and candidate/source binding);
both have fixes and regression tests.

No build, GPU run, service, setting, live queue or other packet tree changed.
The initial `git pull --rebase` refused unrelated dirty files; a fetch confirmed
`main` matched `origin/main`. Those unrelated files were neither stashed nor
included. The final queue receipts and test logs are in
`experiments/own-xpu-runtime/ops/packet97-orchestration/`.

Final decision: [`d27742791d5b859d`](../experiments/own-xpu-runtime/ops/packet97-orchestration/decisions/d27742791d5b859d.json).
All **24 proposed jobs** pass their real CPU plan on temporary queues: six
composite jobs and eighteen conditional leave-one-out jobs. Both proposal sets
bind that same decision. The frozen decision also validates and reconstructs
exactly from its qualified sources. Receipts:
[composite plans](../experiments/own-xpu-runtime/ops/packet97-orchestration/composite-plans.json),
[leave-one-out plans](../experiments/own-xpu-runtime/ops/packet97-orchestration/leave-one-out-plans.json),
[orchestration tests](../experiments/own-xpu-runtime/ops/packet97-orchestration/python-tests-97b.log),
[packet tests](../experiments/own-xpu-runtime/ops/packet97-orchestration/packet-tests-97b.log),
[decision check](../experiments/own-xpu-runtime/ops/packet97-orchestration/decision-check.log).
`composition_ready=true`; `ready=false` because the composite has no device
receipts yet. No storage gate or full-chain requirement was waived.
