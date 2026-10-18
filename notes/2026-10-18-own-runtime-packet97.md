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

## Coordinator: packet97-chain KD refusal (2026-10-18 05:13 UTC)
- The chain for decision `f1e5d7f47fc0fe54` launched at 04:53 after packet 97d's identical-selection readiness. K0, K1a, K1b, K2 and W0p passed.
- **KD failed before any device execution.** Its host reference refused: "p90 cached layout requires sealed 24/24 rank1-draft resident r5 parallel context4096 prepared path". KD's host-reference path does not accept E1's half-cache layout.
- The CPU gates (256 startup checks) never exercised KD's host-reference path with E1 selected.
- Fault count unchanged (2). The coordinator drained the teardown record and archived the stale lane-A marker before lane B's running screen reached teardown (lane-A render nodes had no holders).
- Codex 97e: fix the KD host reference for half-cache, add an every-window CPU startup gate for all 128 compositions, and allow a fresh chain folder for the same decision. Evidence in `build/device-cards01-a` is kept as history.

## Packet97e — KD host-reference repair and a fresh chain directory

The failure was a real unsupported startup combination, not a device fault.
`draft_window.py` passed `--rank 1 --context 4096` but omitted `--memory` and
`--draft-rank`. The native defaults were `layer-streaming` and draft rank 0;
`Engine::prepared_path` was false. `run_draft_capture` constructs a rank-1
24/24 target plan and then runs only `DraftRuntime` on the frozen captured target
streams. E1's guard correctly requires resident, prepared, rank-1-draft, 24/24,
r5/parallel, context4096. The earlier full-shape test explicitly supplied those
working settings and therefore never tested KD's actual command.

Simply switching this CPU reference to resident mode is not viable under the
8 GiB bound. The selected rank-1 resident startup accounts for **31,581,735,626
bytes** in the existing full-shape census. It loads the unused target half in
addition to the draft. The CPU reference does not execute those target layers.
The guard and both runtime binaries therefore remain unchanged.

The new `kd_reference.py` binds a draft-only selection to the original target
selection hash. It projects only target expert storage, target head storage,
target HC norm fusion and target host retirement to their baseline choices.
It preserves every draft choice, route/recurrence choice, dispatch, tensor,
context and arithmetic operation. The draft uses its existing expanded Q6
head and the same 91,392 computed rows. A packed target head may change how
much unused head storage the standalone capture holds, never the computed
prefix. The real target windows continue to use the full original selection.
This is a bounded draft reference, not evidence that target E1 ran on the CPU.

`kd_window97e.py` retains the original complete CPU-reference comparison,
proposal-argmax check, two fresh owners, final-state comparison, safe teardown
and memory watchdog. Each owner must also prove the exact projected hash,
unchanged draft choices and no target mutable aliases. Its raw receipt keeps
its true projected hash. `submission97e.py` extends the byte-pinned original
replay validator: only the two KD native receipts can use that hash, and only
after checking the receipt-bound target-to-reference mapping and matching draft
kernel identities. All target/window, output, acceptance and timing gates remain
in force. Use `submission97e.py` for later evidence preparation and
`submission_cli97e.py` for a later submission of this new chain;
no submission was made here.

`chain97e.py` is a narrow entry adapter: it keeps the original queue/window
code, changes the child entry to itself and installs the new KD implementation.
This leaves the original files pinned by all 128 screen seals untouched. The
fresh-chain preparer accepts a new `device-cards01-b` (or later `-c`) only for
the already selected composition, saves the preceding chain seal, registers the
new output, seals current chain tools, and reruns readiness. It never imports
completed windows, changes a frozen decision or resumes an occupied directory.
The old `device-cards01-a` is history.

The new startup gate executes the original window parser, manifest-derived caps
and retention guards, then obtains native argv from the real `Transport`.
It uses production `parse`, `Engine`, `DraftRuntime`, allocation and capture
with full dimensions (hidden 2560, vocabulary 248320, context4096); only payload
reads and the backend are mocked. Every view gets every window. Selection-free
K fixtures are shared after executing their real CPU paths; K0 explicitly uses
its existing CPU structural shim because JIT has no CPU analogue. K2's host
fixture cannot request device timing, so it runs its exact fixture path. The
actual W0p CPU shared-memory handshake also runs. KD is checked for both host
and device argument sets, and its draft-kernel identity must equal that of the
selected resident draft. The old unprojected E1 command must refuse with the
original guard message. Sources are snapshotted before the gate and must remain
unchanged until it finishes.

The initial pull refused the shared checkout's unrelated edits. Fetch showed
`main` equal to `origin/main`; nothing was stashed or reset. Read-only parallel
review caught the suite-cap and submission-replay gaps before final readiness;
both have regression coverage. No GPU, service, sudo, setting or live queue ran.
The frozen decisions, 128 screen seals, both binaries and old chain files have
414 recorded identities for a final unchanged-byte check.

Final CPU gate: **1,408/1,408 windows passed** (128 compositions × eleven
windows) in **756.482 seconds (12 minutes 36 seconds)**; maximum child RSS
was **1,249,832 KiB (about 1.2 GiB)**. The required old E1 startup refused
before the repaired path passed. The new fixture build occupies about 22 MB;
the original host/device binaries were not rebuilt. The focused combined
Python suite passed **152 tests**. The standalone submission entry points also
passed their CLI checks; no evidence was submitted.

Readiness is **true** for unchanged decision `f1e5d7f47fc0fe54`, with
`chain_output=device-cards01-b` and unit `packet97-chain-b`. All five preparation
checks and identical-selection evidence pass. The output directory remains
absent until the coordinator explicitly launches it. Later `-c` is supported
by the same fresh-folder preparation; an occupied directory is rejected.
The exact executable manual command is the `chain_command` string in
`experiments/own-xpu-runtime/ops/packet97-orchestration/ready.json`.

Evidence: `stage2/packet97-record-bundle/startup97e.json` and
`evidence/startup97e-runs.json.gz` contain the full coverage and source hashes;
`evidence/startup97e.log` retains progress, and
`evidence/packet97e-old-e1-refusal.json` retains the regression trigger.
The new readiness and verification logs are under `ops/packet97-orchestration/`.
The CPU fixture proves guards, shapes and draft-kernel identity, not device
output equality. The full unchanged device exactness chain remains pending.

[Packet97e closeout](../experiments/own-xpu-runtime/stage2/packet97-record-bundle/PACKET97E-CLOSEOUT.md)
records the repair's scope and revisit conditions.
