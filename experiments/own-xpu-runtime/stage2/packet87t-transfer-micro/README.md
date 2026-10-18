# Packet87t: head-split transfer microbenchmark

**CPU preparation; device measurements pending.** One proposed lane-B job
measures transport without loading a model. The native build and the host-backed
two-process protocol checks do not establish device latency or a model gain.
[Task note](../../../../notes/2026-10-18-own-runtime-packet87t.md).

The proposal was shipped after compilation and temporary-queue planning:
[`proposed-p87t-micro-B.txt`](../../ops/lane-queue/proposed-p87t-micro-B.txt).
Preparation never installs it into a live queue or launches it. The coordinator
owns the existing systemd lane runner, fault review and authorized device window.
The job has a 300-second watchdog, cooperative stop, no retries and a shared drain
permit. Memory admission requires 10 GiB available (8 GiB reserve plus 2 GiB
process-tree budget) before acquiring the v4 lane-B lease and again before launch.
Root needs 12 GiB plus 32 MiB for receipts. This tiny job allocates about 283 KiB
of device buffers per card, plus a 20 KiB pinned slab and ordinary runtime costs.

## Measurement

Two processes fork **before** either initializes SYCL. The parent is rank0-like
on physical card 2 (`43:00.0`); the child is rank1-like on card 3 (`47:00.0`). Each
sets its own pre-open BDF filter and uses native index 0. The wrapper checks each
process's DRM ownership, their union, and successful teardown before release.

| Case | Direction | What is timed |
| --- | --- | --- |
| hidden | card3 → host → card2 | 5,120-byte BF16 vector, D2H wait, staging/publication, H2D wait |
| best8 / best16 | card2 → host → card3 | 8/16-byte local-best return through the same ordered path |
| pipeline20480 | card2 → host → card3 | Existing stream handoff: 20,480-byte readback, host vector/shared copy, original mailbox/handover, queued 4-byte token plus stream uploads |
| mailbox20480 | parent → child | Original handover and request/receipt boundary without DMA, for packet85 calibration |

Each transport case runs idle and with a compute kernel enqueued on **each
card's existing in-order queue**. The workload uses 65,536 integer work items,
2,048 dependent updates per item, and a separate 256 KiB output. No target
arithmetic, model weights or inputs are involved. The real queue ordering means
copies cannot bypass earlier compute on their own card. Cross-card activity
can overlap; no second queue or unmeasured overlap saving is invented. Each
sample records whether compute remained pending at export/import. Inspect those
counts before describing actual overlap.

Cases, idle/compute order and compute enqueue order alternate. Ten repetitions
initialize the kernels/queues/tiny buffers and are discarded. Every cell has
200 measured repetitions: 1,800 retained samples total. Timing uses the common
host monotonic clock, from source copy issue through destination completion,
not zero-width attribution events. The final receipt has explicit drain proof.
Output writes, destination byte checking and event cleanup after data-ready are
outside the reported critical path. Source-side event retirement and staging
are inside it, following the engine readback path. Destination data is poisoned
before every transfer; readback checks every transferred byte and the pipeline
token. Pinned slabs are never reused before the owning event completes.

The copies of packet97 owner, single-device queue, event retirement, spin wait
and native mailbox sources are byte-identical; see [source-lineage.json](source-lineage.json).
The small inherited SYCL hook is checked against packet97's source closure.
No parent orchestration output is pinned. The copied compile-turn gate is
packet94's unchanged file. The linked parent wait-policy object has byte zero
for `p56x::sleep20`; this build uses the same spin policy. All source copies,
compiler commands, binary hash and runner dependencies are bound in receipts.

## Modeling and decision

`report.py` requires the passed, drained, hash-matching device receipt before
writing `RESULT.json` and `DECISION.md`. It reports median, nearest-rank p90,
mean and sample count for the total, export, import and host-boundary times.
It executes packet87's six original pure modeling functions extracted by AST,
and first reproduces both original optima exactly. Packet87/85 files are frozen.

The forecast retains packet87's **packet77 control** and row-scaling assumptions;
it is not a prediction based on packet97's current model throughput. New `E/I/V`
replace the old host publication proxies, avoiding double counting:

- `E`: hidden-vector source issue to parent receipt of the completed export;
- `I`: parent handover and destination upload through data-ready;
- `V`: complete measured 16-byte return plus packet87's final collection proxy.

The return's H2D to rank1 is conservative against packet87's CPU-only final
merge design. New rank1-local argmax readback/merge arithmetic remains an
implementation gate; this micro only checks payload transport. Compare the
mailbox-only boundary with packet85's 11.620 µs **mean** (its median is 12.042 µs),
not with the whole DMA round trip. The calibration omits model-state acceptance
and checks; it is a transport-boundary calibration, not a complete target half.

The **idle median** prices added transfers because the model already accounts
for compute in A/B/D. Busy-total scenarios explicitly include outstanding
synthetic compute: report them as pessimistic contention sensitivities, not a
second charge in the design decision. Component p90 costs are sensitivity inputs,
not the p90 of model throughput. No output token or measured speed is claimed.

Reoptimize all 256-row splits and the no-split choice. A prediction of at least
+0.5% versus the matched measured control produces a conditional `DESIGN.md`;
smaller gains produce a local `DO-NOT-REPEAT.md` and evidence-linked closeout.
Even an eligible design needs full-shape memory admission, unchanged logit/tie/
finite-status arithmetic, deterministic output and fresh-server performance gates
before an engine seal or performance promotion.

## CPU reproduction

Run from the repository root, with stdin closed:

```bash
P=experiments/own-xpu-runtime/stage2/packet87t-transfer-micro
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/build_engine.py" </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/cpu_protocol.py" </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/test_packet.py" </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/run_micro.py" --plan </dev/null
```

The CPU protocol compiles the actual micro control flow with a host-backed owner
substitute, runs both processes and validates all 1,800 samples; its timings are
discarded. This tests ordering, poisoning, payloads and teardown, not DMA or Xe
compute. Native build and CPU scratch together remain below 5 MB. The 200 MB
build ceiling is enforced. Generated objects, executables and CPU sample scratch
stay in ignored `build/`; rebuild commands and SHA-256 receipts are retained.
