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
QSA passes GNU and Intel leaf checks twice. Finite cross-compiler hashes match;
NaN payloads are compared against each compiler's unchanged production, whose
exceptional payload choices differ between compilers.

The proposal is narrowed to **QSA only**, two fresh lane-B processes. Both
128-token and 4096-token cases use matching production/candidate launch extents.
This is a deliberate quality-gate outcome, not completion of a lossless GDN
implementation. The full per-layer specialisation objective remains open.

## Final CPU evidence and handoff

All three builds pass: GNU host, Intel host, and SYCL device compilation (no
device binary executed). Each frozen parent object set relinks to its original
executable hash before reuse. Build storage is **67,228,967 bytes**; peak
complete-layer CPU RSS is **1,253,980 KiB** (about 1.2 GiB). The build scripts
impose an 8 GiB address-space limit and take packet94's serial compiler turn.

- [Complete-layer receipt](../experiments/own-xpu-runtime/stage2/packet107-specialised-layers/evidence/cpu-layers.json):
  GNU twice and Intel twice, **1,216 byte comparisons per process**, four serial
  tokens per layer, all producer outputs and complete production mutable
  allocations. All four output identities match. The Intel harness/candidates
  are newly compiled; unchanged operators link the frozen GNU objects. Intel
  leaf tests separately compile their unchanged production references.
- [Leaf receipt](../experiments/own-xpu-runtime/stage2/packet107-specialised-layers/evidence/cpu-leaf.json):
  **58 QSA cases per process**, twice under each compiler. Fifty-four compare
  raw FP32 values before BF16/gating as well as complete output buffers; four
  check inactive/error/position guards. Cases include split boundaries, 128 and
  4096 occupied tokens, signed zeros, infinity and NaN payloads. Instrumented
  pre-BF16 expressions must also match the uninstrumented candidate. Finite
  cross-compiler hashes match. Each compiler's exceptional bytes match its own
  production exactly; GNU and Intel production themselves choose different
  exceptional payloads. GDN remains explicitly failed, not hidden by aggregate
  finite-layer success.
- Eight qualification tests pass: two-owner requirement, exact threshold,
  one weak owner, context separation, identity drift, inexact output, missing
  pair and broken event accounting.
- Both direct `--plan` checks and both jobs in a **temporary** lane queue pass.
  The proposal is
  [proposed-p107-micro-B.txt](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p107-micro-B.txt).
  Nothing was installed in the live queue. The native device entry refuses GDN.

[Code-only cost accounting](../experiments/own-xpu-runtime/stage2/packet107-specialised-layers/evidence/code-cost.json):
QSA removes **2,359,296 logical global KV-read bytes** at 128 selected tokens,
and **37,748,736 bytes** at 2048 selected tokens in the 4096-token case. These
are source access counts, not measured DRAM traffic: production caches may
already serve repeated reads. Dividing by an assumed 550 GB/s gives **4.29 µs**
and **68.63 µs**, respectively, only a bandwidth arithmetic estimate. It cannot
justify an 80 µs short-context gain by itself. Both variants still use three
attention kernels; **zero host/device waits are removed**. The remaining
hypothesis is lower load/dispatch instruction cost; it may regress under local
memory pressure. The device gate, not this estimate, decides.

GDN would remove **3,040 repeated norm trees**, 389,120 products and 583,680
divisions, and reduce head-gate evaluations from 1,536 to 48. It adds one kernel
and roughly 806 KB of logical global preparation/input traffic; full BF16 state
read/write traffic remains 3,145,728 bytes. No positive microsecond estimate is
supported, and exactness already closes it.

Reproduction, from the repo root, with stdin from `/dev/null`:

```sh
P=experiments/own-xpu-runtime/stage2/packet107-specialised-layers
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/build_engine.py" --mode gnu-host
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/build_engine.py" --mode intel-host
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/build_engine.py" --mode device
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/cpu_leaf.py"
# cpu_layers.py requires new output directories; do not overwrite old receipts.
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/cpu_layers.py"
nice -n 19 taskset -c 8-15,24-31 python3 -B -m unittest discover -s "$P" -p test_qualification.py
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/seal.py"
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/run_micro.py" --lane B --owner 1 --plan
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/run_micro.py" --lane B --owner 2 --plan
```

No device speed, model oracle or model integration pass is claimed. The complete
specialised-layer lever is not finished: this packet retains one closed GDN
implementation and one qualified CPU QSA candidate for measurement.
