# Packet56w: bounded spinning before host sleep

Packet56w is built, CPU-checked and sealed for the coordinator's A/B screen.
No GPU, model load, service, sudo, power/memory/swap/page-cache change or reboot
ran. CPU helpers and compilers ran at nice19 on cores 8–15,24–31 with
`python3 -B`; compilation was serial. Other jobs' files and sealed packets
were left alone. The initial `git pull --rebase` was blocked by concurrent
packet59 edits; a fetch showed HEAD equal to origin/main. After that worker
committed, `git pull --rebase` succeeded and was already up to date.

## Change and reason

The brief reports packet57 attribution beating its control on all twelve
prompts, with fewer rank-0 sleeps. Those are motivating observations from the
reviewer, not packet56w measurements or a causal conclusion.

The new [packet56w folder](../experiments/own-xpu-runtime/stage2/packet56w-spin/README.md)
starts from packet56. `wait_change()` now polls with PAUSE for up to 250 µs
before its existing 100 µs futex wait. The shared helper covers mailbox
requests, replies and draft publication, including accept and miss rollback.
The device backend gets the same 250 µs budget before its existing 1 ms sleep.
Each invocation gets one spin budget, not a new budget after every sleep.
Publication acquire/release semantics, cancellation, abort, deadlines, errors
and the final device completion wait remain in place.

The packet57 audit found identical mailbox and device wait loops. It also
found one relevant queue difference: only draft rank 1 receives `--draft-mtp`,
so token mode enables queue profiling on rank 1; attribution additionally
enables it on rank 0. Packet56w carries over the rank-0 profiling property
without event collection, timing reads or output. The property can affect
driver event completion behavior; that effect remains unmeasured. The A/B
screen tests the spin and queue property together, not their separate effects.
Packet57's other differences are event bookkeeping and timing output after
existing completion checks. They are not adopted.

Kernels, arithmetic, submission order, target fixtures, draft prefix, target
split, BF16 KV, dispatch, selection, memory budget and packet49 oracle are
unchanged. [Parent manifest](../experiments/own-xpu-runtime/stage2/packet56w-spin/parent-source-manifest.json),
[source audit](../experiments/own-xpu-runtime/stage2/packet56w-spin/evidence/source-delta.json),
[focused patch](../experiments/own-xpu-runtime/stage2/packet56w-spin/evidence/native-waits.patch)
and [packet57 diff](../experiments/own-xpu-runtime/stage2/packet56w-spin/evidence/packet57-wait-audit.diff)
retain the identities and inspection.

## Lean checks and seal

- Device engine and CPU controller/fault binaries built successfully.
- Existing controller comparison: **1,123 cases passed**, including 1,093
  ternary patterns, 24 long random cases and overlap/EOS cases. Tokens, guesses,
  hit/miss decisions, counts, committed state and fixtures match.
- Existing mailbox fault test: **five checks passed**, including 32 repeated
  requests, timeout, cooperative stop, peer failure and queued-command abort.
- One fixed controller fixture: **765 bytes identical** to a fresh parent
  controller binary. Raw JSON and canonical token/state/fixture/count bytes
  are retained. This is synthetic CPU evidence, not model certification.
- Screen seal and CPU-only `--plan` passed, rechecking source, native binary,
  runtime configuration, byte fixture and existing oracle bindings. The first
  plan invocation omitted a required CLI date and was rejected before work;
  inspection also corrected the documented output to the screen's required
  evidence root. The successful plan uses the epoch only as a parser value
  with `--plan`, never as a device admission or fault waiver.

Commands and receipts are in [CPU preparation](../experiments/own-xpu-runtime/stage2/packet56w-spin/README.md#lean-cpu-preparation).
The seal is `ce0b53bc4fa84a41fb7597fd001da7435b307a29a3ba65de3416ae2cdcba4988`.
The engine is `b6a78f44a7174ad2d4b22da804227cd4c4f9668cd230368a5ccbb2338c95c169`.
Compiler logs and commands are retained under the packet's `evidence/build/`.
Only this packet's regenerable object files were removed: 29,938,634 bytes;
the remaining build is 37,910,098 bytes. RoPE is a read-only byte-identical
link to packet56; the unchanged draft manifest is copied and sealed.

A final Git-retention check identified the inherited generated CPU RoPE header
as the sole source path outside Git. It already exists in packet45's build;
no parent was changed. A small preparation helper now reconstructs its exact
12,582,900 bytes from the retained RoPE input and checks the existing seal's
hash, restoring only this candidate's local read-only link on this host.
[Restoration details](../experiments/own-xpu-runtime/stage2/packet56w-spin/ARTIFACT-RETENTION.md)
and a derivation receipt are retained. This adds no new header blob and changes
neither the sealed sources, binary nor seal. The build-size figure above is
the candidate's own retained bytes, excluding that shared read-only input.

## Coordinator handoff

Run the [exact screen command](../experiments/own-xpu-runtime/stage2/packet56w-spin/WINDOW.md)
with the existing packet56 two-card profile and `screen-seal.json`. It checks
the incident prompt and all 12 × 128 suite tokens against packet49. Use the
same affinity and priority for the packet56 control. The coordinator supplies
the actual reviewed fault boundary and owns device admission and teardown.
No screen ran here, and no device exactness, speed improvement or record is
claimed. A promising screen still needs the full sealed qualification chain.


## Full sealed chain and submission tooling — October 17, CPU-only

The existing screen is promising: **48.831100403687785 class-balanced tok/s**,
48.904244919074586 all-prompt, acceptance 0.7874015748031495, and exact answers
for the separate incident check plus all twelve suite prompts. The brief's
matched packet56 controls were 46.792 and 46.796. This remains screen evidence;
it is not a record or a completed qualification chain. The compact
[screen context receipt](../experiments/own-xpu-runtime/stage2/packet56w-chain/evidence/screen-context.json)
pins the retained raw summary without copying its large request traces.

Decisions made without an approval pause:

- Create **packet56w-chain**, leaving packet56w-spin's source, screened binary
  and screen seal unchanged. The original screen seal says screen-only and
  must not be overwritten. The chain has a separate admission seal.
- Use the exact screened engine
  `b6a78f44a7174ad2d4b22da804227cd4c4f9668cd230368a5ccbb2338c95c169`.
  No kernel, arithmetic, compiler or native controller change is made.
  Reuse packet56's unchanged fixture binaries and CPU draft reference as
  read-only links. Their provenance is explicit; they are not new builds.
- Reuse packet56's two already completed draft-head windows, checking their
  original bytes, two distinct process identities, summaries and current boot.
  The calibrated prefix has not changed. These checks passed on this boot.
  All eleven full-chain windows will produce fresh packet56w outputs.
- Preserve the exact order K0 → K1a → K1b → K2 → W0p → KD → W2m → WS → WSs →
  WS128x → WS128, the packet49 oracle, split 23/25, draft rank 1, full BF16 KV,
  4096-token capacity, metric definitions and owner-authorized 128-token scope.
  The strict 512-token gate stays false. No new target oracle is started.
- Keep the PF_EXITING-aware memory sensor. Chain rank/KD supervision uses it
  so a dying task's missing RssAnon is distinguished from malformed live-task
  information. Device binaries and arithmetic are unchanged.
- Use a new build view at
  `/home/steve/own-xpu-runtime-results/packet56w-spin/build`, with the registered
  chain output `device-cards01-a`. `prepare_chain.py` restores only checked
  read-only links; it refuses replacement or changes after the chain starts.
- Keep submission helpers local. They bind both the chain and screen seals,
  retain all packet56 evidence checks, and read the current shared floor
  **46.96269702286488**, reference `cmvcf84kb06r2le0174bgk16l`. Generated payload
  notes name the **91,392-row draft-head prefix** and **250 µs bounded spin**,
  including rank-0 queue profiling without timing reads. No attribution to
  spin alone is claimed. Posting rechecks the floor; historical replay remains
  reproducible.
- Preserve packet56's storage envelope. At the first check, about 11.96 GB was
  free against 15,446,804,480 bytes required, about **3.48 GB short**. Admission
  refuses. Do not weaken the 8 GB free floor, 1.5 GB build reserve or complete
  chain reserve. No cleanup of another job's evidence is authorized here.
- Keep changes confined to the new chain folder and this requested note.
  No live device state changed, and CURRENT.md/shared record files are untouched.

The initial `git pull --rebase` refused because packet60 had concurrent
uncommitted changes. A fetch showed no incoming commits; those edits were
left alone. Work stays on main, with explicit path commits pushed immediately.

Lean checks before sealing: **29 local tests passed**, covering submission
replay, changed pins, current-floor enforcement, prefix/spin notes, queue
order, oracle paths, no-launch planning and PF_EXITING. The existing shared
submission tests passed **128 tests and 29 subtests**. Python syntax checks,
shell syntax and all 28 retained binary/input links passed. The system Python
has no pytest; tests use the existing vllm-xpu venv's python3. An initial
shared-test collection needed `PYTHONPATH=scripts`; the corrected run passed.
All Python commands use `-B`, nice19 and cores 8–15,24–31. No device executable,
model payload, sudo, service, setting change, reboot, external dry-run or real
submission was used. No process was killed.

Exact commands are in [WINDOW.md](../experiments/own-xpu-runtime/stage2/packet56w-chain/WINDOW.md)
and [SUBMISSION.md](../experiments/own-xpu-runtime/stage2/packet56w-chain/SUBMISSION.md).
The implementation commit is followed by its immutable chain seal, submission
pins and saved CPU plan verification. Device qualification and a real record
remain the coordinator's next work, after storage admission passes.


### Final chain seal and handoff

Implementation commit **7462ccc84** was pushed immediately. The final chain
seal is **47e97a92d0aee2ba8705adfb5e5c5b748809ef9072992480536e66364e5d0569**.
It preserves screen seal
`ce0b53bc4fa84a41fb7597fd001da7435b307a29a3ba65de3416ae2cdcba4988`
and the original screened engine hash above. Independent seal verification
passed in 0.27 seconds. Two in-memory negative checks also refused a changed
screen-seal digest and a changed engine digest; no real file was altered.

The saved [chain plan](../experiments/own-xpu-runtime/stage2/packet56w-chain/evidence/chain-plan.json)
passed all eleven command mappings, live immutable oracle completion checks,
parent head prerequisites, pinned dispatch and source/binary identities.
The [printed queue plan](../experiments/own-xpu-runtime/stage2/packet56w-chain/evidence/queue-plan.txt)
contains each exact underlying window command. The [CPU validation receipt](../experiments/own-xpu-runtime/stage2/packet56w-chain/evidence/cpu-validation.json)
records the test commands/counts, seal and plan hashes, and negative controls.

The final plan's storage sample was **11,927,687,168 bytes
free**, requiring **15,446,804,480 bytes**, a
**3,519,117,312-byte shortfall**. Plan success is not
storage admission. The coordinator's exact chain command is documented but
will refuse until the existing budget fits. No new device window, generated
real payload, external dry-run or submission exists. The chain output path
has not been created.

Git retention checks found no new artifact at or above 1 MiB. The only
inherited generated source outside Git is packet45's `fusion-rope.hpp`, already
covered by packet56w-spin's hash-checked
[restoration instructions](../experiments/own-xpu-runtime/stage2/packet56w-spin/ARTIFACT-RETENTION.md).
All other source-closure paths are retained in Git. Parent and screen trees
remain unchanged. The final seal/pins/evidence commit is pushed immediately
as well. No owner decision is requested.
