# Packet 107: specialised ordinary layers

CPU-only preparation, 2026-10-18. The owner time box is 2.5 hours. No device,
service, live queue, frozen packet, or host setting may change. Build budget:
200 MB, 8 GiB address space, nice 19, CPUs 8–15/24–31, closed stdin, one
compiler through packet94's compiler turn. Commands use `python3 -B`.

The initial `git pull --rebase` refused the pre-existing dirty worktree.
`git fetch origin main` then showed HEAD and origin/main identical (0/0).
Other work stays untouched; commits use explicit `git commit --only --` paths
and are pushed immediately.

## Decision and preregistration

Use ordinary GDN layer 4 and QSA layer 3 from packet97's source bundle, with
its copied selection and dispatch. Arithmetic stays `iq3-p49-split32-v1`.
The 56.087 tok/s record and about 15.6 ms hit cycle are the brief's baseline;
this packet claims no device result. Parent orchestration outputs are not pins.

Read DESIGN.md, the October 17 IQ3 speed roadmap, and the negative records
for packets 34, 46, 54, 60 and 94. Packet46 already tested this pair; launch
fusion saved under 8 µs, and collapsing norm parallelism regressed. Packet94's
repeated reductions lost 23%. Do not repeat either mechanism.

The new GDN arm computes each key-head norm and each value-head gate once,
then feeds the unchanged parallel recurrent updates. The QSA arm shares one
BF16 K/V tile among four query heads while retaining each head's score,
softmax, value and split32 reduction order. No reduction is duplicated to
avoid a launch. Mutable expert IDs and QSA selected indices remain inputs;
only their addressing rules and topology may be compile-time constants.

CPU exactness compares complete layer outputs and recurrent/KV state over
consecutive tokens with independent fresh GNU and Intel processes. Device
exactness remains a separate gate. The proposed single-card lane-B micro
alternates production/specialised and specialised/production order at actual
shapes, checks output/state equality outside timing, and repeats with a fresh
process. Integration requires at least 80 µs saved per layer in both processes;
160 µs is the upper target. Anything below 80 µs closes without integration.
Synthetic weights/state are diagnostic, never a model speed result.

Implementation and verification are in progress. Subsequent milestones append
exact commands, code-derived traffic counts, evidence and limitations here.

## Implementation milestone

The first GNU complete-layer run passed GDN's four consecutive tokens, then
refused the QSA binding contract: the planner appends active/error to its five
inputs. Correcting that binding map passed **1,216 complete-layer byte checks**,
with four different expert sets in each layer. The initial refusal is retained
under `evidence/cpu-gnu-initial`; it did not touch a device.

The stronger leaf gate passed both GNU arms. Intel exposed a GDN NaN payload
change (`0x7fc1` to `0x7fc0`) after all finite cases passed. Keeping the original
four-row loop and strict exception handling did not fix it. GDN is closed;
its failed code and exact byte offsets are retained. The device entry refuses
it, rather than hiding the difference behind the finite full-layer pass.
QSA passes GNU and Intel leaf checks twice, including cross-compiler hashes.

The proposal is narrowed to **QSA only**, two fresh lane-B processes. Both
128-token and 4096-token cases use matching production/candidate launch extents.
This is a deliberate quality-gate outcome, not completion of a lossless GDN
implementation. The full per-layer specialisation objective remains open.
