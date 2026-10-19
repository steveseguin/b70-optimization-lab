# Packet58al: demand-transfer build preparation

October 19, 2026; bounded CPU-only preparation during the one-card timing
session. Started at 03:09 UTC on `steve-b70s`. No build, GPU/native execution,
model/GGUF read, service, sudo, setting change or queue edit. Existing packets,
screen evidence and ops were read-only. Helper work used nice19, cores
8–15/24–31, Python `-B`, closed command stdin and a 2 GiB audit address-space
cap. No GPU recovery or inspection was attempted by this task.

The [design packet](../experiments/own-xpu-runtime/stage2/packet58al-demand-transfer-prep/README.md)
and [ready build brief](../experiments/own-xpu-runtime/stage2/packet58al-demand-transfer-prep/briefs/build.md)
specify one candidate for packet58am: copy known misses on BCS while resident
expert slots compute, then consume missing slots and combine in the original
order. Two banks hold at most 64 packed experts (126,156,800 bytes). Each entry
stays owned until its consumers finish; retained bytes can replace a later
policy-selected host transfer with a device copy. Full banks fall back to the
original zero-copy path. No cache-size, arithmetic or precision change.

The parent has an important trap: its ordinary copy call immediately inserts
a compute barrier. The new mechanism needs separate owned demand events and
a barrier only before the missing-slot consumer. Direct zero-copy reads run
on CCS, not BCS. Copies and maintenance share the copy engine; a new queue
does not create another engine. Original slot-indexed outputs and the p109
ordered combination must stay unchanged.

Packet125's tile16 arm already beat its transfer pipeline (187.0/185.8 versus
192.2/194.9 µs). Its masks were simulated, although router IDs were real. This
proposal instead requires actual published misses, resident neighbors and
the full packet58ah composition. All requested one-card closures are mapped
in [DO-NOT-REPEAT](../experiments/own-xpu-runtime/stage2/packet58al-demand-transfer-prep/DO-NOT-REPEAT.md).
A parallel read-only review checked those closures and the stage lifetimes;
it made no edits.

There is also an identity mismatch in the starting brief: packet58ai's
retained source, README and readiness measure packet58ad's 30.396 line, not
packet58ah's full 31.663 composition. Its result can justify a bounded CPU
build hypothesis, but cannot be relabeled a current-parent measurement. The
[decision table](../experiments/own-xpu-runtime/stage2/packet58al-demand-transfer-prep/DECISION.md)
covers ≥1 ms, <0.670 ms, the middle region, unstable, failed and pending
evidence. The same-parent 64-token smoke is explicitly screening; only a
matched unprofiled v5 can decide speed. It cannot reconstruct a 99-interval
census from 64 outputs.

The [real parent audit](../experiments/own-xpu-runtime/stage2/packet58al-demand-transfer-prep/evidence/parent-audit.json)
reconstructs **31.66271941826957 tok/s** from all twelve chain-b WS128
requests. It binds source/result/native argv and retains cold first-request
rows. The first prefill token took **23,457.6 ms**, and that request's
prefill total was **28,124.118482 ms**. A short time ceiling in a data proof
would reject valid parent evidence. The build brief requires no such ceiling,
a real device-binary CPU preparation probe, offline relative-tolerance
checks, and per-op waits at least four times the measured cold phase with
a 300-second minimum initially.

Measured parent output sizes (file metadata only): K1a **4,046,707 bytes**,
K1b **4,046,714**, KD **22,321,118**, WS128 **16,843,381**. The new build must
measure its added schema/storage and keep planned writes no more than three
times the matched measured-volume estimate, above the unchanged **25 GB**
device-job disk floor. CPU preparation stops below **27 GB**. Staging stays
inside the existing device transfer allowance and adds explicit conservative
host backing while preserving the **8 GiB host reserve**.

Validation command:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet58al-demand-transfer-prep/audit.py </dev/null
```

The audit passes all pinned source hashes/ranges and the twelve real requests;
it is not a new model-quality proof or a future demand analyzer. The brief
requires GNU/Intel real-shape bytes, real cold-evidence analyzer replay,
smoke plus one-load v5 with first view warm-up, fresh identities and READY
written last. No READY-for-device marker is issued by this design packet.

At the 03:38 UTC observation, no completed packet58ai `census-analysis.json`
was present. No miss-cost or overlap number is invented. Latest poll and
build-release status are retained in
[evidence/poll.json](../experiments/own-xpu-runtime/stage2/packet58al-demand-transfer-prep/evidence/poll.json).
The prep keeps build release withheld until a qualified verdict arrives.

The later 03:42 UTC poll still has no completed census. The owning note records
that the b-smoke attempt refused **before device work** at 03:34:35 because
its coordinator gate used an old job name. The c-smoke identity repair is
committed, with fresh proposal checks passing; that preparation is not a
device verdict. Its readiness hash, repair receipt and the failed attempt's
exit receipt are now pinned in the poll. No partial/missing number is used
to build or close rank 4. The initial design commit `2952181a5` was pushed
immediately; the final update retains this newer observation. Preparation
finished inside the 60-minute limit.

Final audit peak RSS was approximately **18 MiB**. It also checks the proposed
staging/host arithmetic against the parent admission metadata, explicitly
leaving real simultaneous-lifetime and live admission gates pending. Document
links and Git whitespace checks pass. Review clarified that exhaustive masks
apply to ownership/address bookkeeping, with representative full-shape
arithmetic cases, and that v5 disables event profiling in both arms. New-schema
storage sizes measured from synthetic serialization stay labeled as such
until the actual smoke replaces that estimate.

Git: initial `git pull --rebase` refused unrelated dirty files. Fetch showed
the coordinator's local review commit ahead of origin; a later fetch confirmed
HEAD == origin/main at `ca9822f755899d9b0aec1b96ed8298fe1d8f4202`.
Only this packet and this note belong to the prep commit. No live state was
changed, so CURRENT's running-lane authority is left to the coordinator.
