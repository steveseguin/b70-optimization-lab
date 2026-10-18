# Packet116: exact QSA schedule

The current attention path already splits work by head and 32 selected positions.
The new schedule keeps that arithmetic and shares more of the work within each
group. Selection shares its rank scan across the subgroup. This is CPU-only
preparation; no device equality or speed is measured by this task.

The [source audit](../experiments/own-xpu-runtime/stage2/packet116-qsa-schedule/AUDIT.md)
records the selected packet103 kernels, the fixed `iq3-p49-split32-v1`
reduction trees, and every relevant negative-history file. The source base
is packet111 after the owner's packet111r decision (`9b49c03e7`).
The starting `git pull --rebase` refused unrelated dirty orchestration files;
`git fetch origin` confirmed HEAD and origin/main both
`b7b35ef9bc6f8ea7783e2548812b7925ce720e9c`.

## Prepared experiment

- Target attention: keep admit and combine unchanged. The fixed32 tile uses
  256 threads/eight subgroups instead of128/four. Each subgroup computes four
  scores instead ofeight. The original128
  threads retain the original vector2 value arithmetic and storage; the extra
 128 threads help score positions. Two lower-liveness tree variants were
  rejected after compiler-specific NaN payload differences; see the
  [closeout](../experiments/own-xpu-runtime/stage2/packet116-qsa-schedule/TREE-CLOSEOUT.md).
- Selection: keep the128-leaf adjacent score tree and ordered four-head sum.
  Replace local-memory tree barriers by explicit subgroup shuffles. Share the
  full finite scan and integer rank over32 lanes; descending score and
  ascending block-ID ties are unchanged. The complete selected-ID suffix stays
  covered, including partial pooled tails and rejected inputs.
- Micro first: copy packet110's complete-layer harness in a new directory.
  Compare whole state, including scratch immediately after the changed
  operations. Contexts128 and4096, both orders, two fresh processes.
  Sum every event per class/invocation. Each fresh process must have combined
  attention+selection median at128 at most0.6 times production.
- Prepare the packet111r one-load v5 bracket in parallel, with exactly
  `qsa_schedule=production|p116`. Its proposal remains conditional on the
  independent two-process micro gate. Only the views that will run get startup
  and host-reference checks. Both native exec boundaries check resource limits.

## Boundaries

All existing packets, screen files and operational files are frozen. Only new
proposed queue files may be written; no live queue edits. No GPU, services,
sudo, secrets or host-setting changes. Only our own idle CPU wrappers were
stopped when the shared compiler gate was held; no other process was stopped. CPU work uses
nice19, affinity8–15/24–31, Python without bytecode and closed stdin. Compiler
turns use packet94's shared lock. CPU CLI caps are8GiB, never import side
effects. Root must retain25GB free and packet116 builds stay below250MB.

## Status

Source audit is pushed in `0a16b680c`. The final scalar operator gate passes
8,764 exact checks per fresh process, twice under GNU and twice under Intel.
It compares all allocated state and pre-gate FP32 values, with both selection
orders, ties, partial blocks, signed zero, NaN/Inf and invalid controls.
Compiler-specific NaN bytes are compared against each compiler’s production;
cross-compiler NaN hashes are not required to match. CPU exceptional attention
inputs use the unchanged scalar reference body. Device numerator arithmetic
uses the original vector2 body; actual device equality remains mandatory.

The micro is compiled and sealed. Two fresh GNU and two fresh Intel complete-
layer processes each pass 668 byte comparisons, including immediate scratch
checks. Both temporary lane-B queue plans pass. The new
[proposal](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p116-micro-B.txt)
contains two fresh owners: 240 seconds expected and a 1,200-second watchdog
per owner. Its native source/object snapshot is independent of later v5 edits.
The frozen packet110 rope is linked and hash-checked, avoiding another 4 MB
copy. The first plan rejected that link under the packet-local path check;
the final seal binds its frozen target under the repository root and checks
the exact relative link. The rejection is retained.

Device timing and device quality remain pending. No live queue was changed.


## One-load bracket ready

The [conditional v5 proposal](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p116-v5-B.txt)
also passes a temporary lane-B queue plan. It runs five views in one load:
production, p116, production, p116, production. Both inherit packet111r's
combined head split and other fusion; only target QSA scheduling changes.
Expected duration is 900 seconds, with a 3,600-second watchdog. The actual
launch checks the current sealed micro identity and both fresh exact micro
receipts, including the 0.6 threshold, before admission. Direct screen entry
has the same gate. No device performance result exists yet.

All selected-view CPU checks pass: four full-size capture/switch runs, four
reset runs, two fresh protocol brackets, all 22 startup/host-reference paths,
unchanged limits on import, both native pre-exec checks and eight policy tests.
The initial full-shape audit refused inherited kernel types with missing
capture serializers. The new audit fixture explicitly includes their actual
fields; it retains the refusal logs and backtraces and still rejects unknown
types. `v5/evidence/cpu-sequence.json` is the retained failed first sequence,
not the final status. The final individual receipts are bound by
`v5/lineage/screen-seal.json`.

Full-shape captures are retained in four compressed archives with member hash
checks and restoration instructions in `v5/RETENTION.md`. Generated builds
are ignored. Final build size is 121,537,879 bytes (under 250 MB), and root
has 38.8 GB free (above 25 GB). Existing packets and live queues were untouched.
The next action belongs to the coordinator: run the two proposed micros,
then queue v5 only if both pass. Failure closes this schedule without a v5 run.
