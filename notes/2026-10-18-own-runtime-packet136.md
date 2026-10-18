# Packet136 — prepare bundle8 with banked rollback before lane B decides

CPU-only task on `steve-b70s`, October 18. Bundle7's record remains
**58.223834 tok/s**, `cmvdx8urg0068rf01vvb32bcs`. Nothing in this preparation
changes that result or claims a measured improvement.

The new [bundle](../experiments/own-xpu-runtime/stage2/packet136-record-bundle/README.md)
is copied from frozen packet124c. All 182 parent symlinks are preserved,
including `oracle -> ../packet49-integrate/oracle`. Packet133 supplies the lean
orchestration pattern, but its suffix scheduling candidate is absent.

The only new dimension is `rollback_state=copy|banks`. Native selections are
exactly packet131b's `miss=batch` and `miss=banks-batch`; GNU and device runtime
binaries and their source closure are reused by exact hashes. Packet131b's
[bank-state proof](../experiments/own-xpu-runtime/stage2/packet131b-snapshot-banks/EXACTNESS.md)
and eight exact GNU/Intel state transcripts remain the bank-specific CPU
evidence. Arithmetic stays `iq3-p49-split32-v1`; KV stays BF16. No extra device
allocation is admitted. The fixed 80,128-row draft prefix remains tied to
packet114's non-benchmark preregistration, not these speed tests.

The [readiness policy](../experiments/own-xpu-runtime/ops/packet136-orchestration/README.md)
requires both fresh-load lane comparisons and the new composed 12 × 64 smoke.
The bank allocation/prepared-command layout is not switchable in the current
v5 wrapper, so lane A uses v4 C/X/C/X/C, matching packet131b B: twelve cold
128-token prompts plus incident64 per load. Both candidate repeats must beat
every control by at least 0.5% on each lane, control drift must be at most 3%,
and all exact outputs and per-prompt acceptance counts must agree. The B reader
recomputes packet131b's raw receipts; its original 1% study verdict is not used
as this packet's threshold. Native selections, binaries, dispatch and memory
layouts must match across both lanes. Only the memory view label may differ.

The single proposed A file includes the separate smoke and five grid jobs.
Expected duration is 35–55 minutes total. Smoke watchdog is 30 minutes for an
estimated five-minute job; each grid watchdog is 60 minutes for an estimated
6–10-minute job. Each watchdog exceeds four times its estimate. Temporary
planning does not queue anything. The chain output is the fresh
`packet136-record-bundle/build/device-cards01-a`.

The new source-map checks use the runtime safe-path verifier before writing
gates and during admission. Oracle authority is checked separately through
`oracle-binding.json`, `shared_oracle.static_binding()` and the real
`shared_oracle.py --require-complete` subprocess. Both confirm and chain
`--plan` paths run real CPU admission. The extended gate covers all eleven
chain windows and the actual queue loop, including pre-LATE oracle checks.
Six additional entry probes exercise real confirm admission through both
intercepted native rank commands. Synthetic operational receipts are confined
to disposable CPU scratch; they cannot qualify device output or speed.

Submission preparation retains the complete portable evidence/attestation
validator and submission CLI. Notes explicitly supersede
`cmvdx8urg0068rf01vvb32bcs` only after a qualifying faster chain, identify the
quantized compressed model and unchanged verifier, and preserve the honest
owner-authorized 128-token scope: `realistic_final_gate.passed=false`.
No submission occurs in preparation.

## Preparation record

- `git pull --rebase` refused unrelated dirty orchestration files. `git fetch`
  confirmed HEAD and origin/main both at `052e9cf97c59fe5a777c93fc4e5849a61798033b`.
  Those unrelated files remain untouched.
- Before committing, HEAD and origin/main had both advanced to `966006f82`
  through other work in this shared checkout. Packet131b reuse stays pinned
  to its original `052e9cf97` identity. The staged change contains only this
  packet, its new proposal, this note and the current-state entry. Whitespace
  warnings in copied patch/source artifacts and the sealed copied argument
  helper are retained rather than changing their bound bytes for formatting.
- Root had about 37 GB available. The stop threshold is 25 GB; build budget
  is 300 MB. All work uses nice19, CPUs 8–15/24–31, Python `-B`, no stdin.
  CPU-only capped processes use 4 GiB. Runtime imports impose no caps.
- Repeated GNU and Intel bundle7 operator fixtures match the retained bytes.
  The isolated submission and composition tests pass 11/11.
- The first local full-shape compile command exposed an inherited harness
  mismatch: packet131 stores `-c <source>` before `-o`, while the inherited
  startup helper appends its own source after the flags. Local compiler
  metadata is normalized; no frozen file or native runtime binary changes.
  Subsequent compiler admission waits through the whole-host one-card hold
  using `experiments/own-xpu-runtime/ops/compile_turn.py`.
- A read-only parallel audit found one unused copied comparison helper with
  packet131's lane-B/+1% rule. It was removed before sealing; the single live
  readiness rule remains +0.5% on each lane.

Final CPU receipts and pending device status are recorded in
[the final audit](../experiments/own-xpu-runtime/ops/packet136-orchestration/cpu-final.json)
and [readiness](../experiments/own-xpu-runtime/ops/packet136-orchestration/ready.json).
After those CPU gates pass, device evidence reading is the only remaining
orchestration step: `orchestrate.py --evidence-only`, then `verify_ready.py`.
Missing or failed evidence keeps readiness false.

The final run passed 88 tests, 11 subtests and five worker tests. All eleven
chain argument/queue windows passed, with 31 intercepted native argument lists,
twelve queue input preflights and six real oracle checks. All six confirm
entry probes and all six temporary proposal plans passed. The chain plan embeds
its registered library path. Build storage is 256,692,386 bytes; root retained
about 36.9 GB free. CPU readiness is true; chain readiness is false because the
new A smoke/grid are absent and packet131b B is incomplete. The preparation
[closeout](../experiments/own-xpu-runtime/stage2/packet136-record-bundle/CPU-PREPARATION-CLOSEOUT.md)
records the remaining evidence and the reuse boundary.

No GPU work, service, live queue, sudo, power, memory, swap, page-cache change,
reboot or signal to another job is part of this task.

### Four-GiB startup boundary

Both new selections passed the fresh full-size allocation and kernel-consumer
checks. The inherited shared K2 CPU fixture then refused allocation under the
4-GiB address-space cap; it reported a complete safe teardown and zero live
bytes. The failed log is retained as
`stage2/packet136-record-bundle/evidence/startup-k2-4g-refusal.log.gz`.
No device was involved, and the cap was not raised.

K2 has no bank-state selection and its linked binary is unchanged. The final
startup gate therefore verifies packet124c's frozen K2 startup archive and the
exact local binary hash instead of allocating that fixture again. Its row is
explicitly `reused_unchanged=true`, `fresh_native_run=false`. All other shared
CPU fixtures and both compositions' model startup paths run locally. All 22
registered window paths pass, with peak child RSS 1,250,744 KiB. The extended
argument gate still runs K2's real Python entry and original timing-receipt
replay; none of this qualifies a device performance result.
