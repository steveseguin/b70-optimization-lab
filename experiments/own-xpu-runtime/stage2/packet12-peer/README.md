# Packet 12 — two-card peer transport and ordered exchange

**CPU-tested and SYCL compiled/linked only, October 11, 2026. No GPU opened,
device binary invoked or peer bandwidth measured in this task.** See the
[two-card design](../TWO-CARD-TP.md) for placement, arithmetic gates and explicitly
conditional throughput projections. This is our implementation over the lab's
resource owner and Intel platform libraries; no outside runtime is used.

## Prepared measurement

Physical unmasked Level Zero cards **2 and 3**, A=2, B=3. Before allocation,
query peer access both ways and retain names, UUIDs and drivers. The packet-local
[backend](backend.hpp) wraps two SYCL queues in one explicitly owned Level Zero
context. One unchanged `Device/Arena/CopyEngine` owns both allocation sets and
the union of both event ledgers. This avoids foreign allocation IDs, cross-context
event assumptions and premature destruction by an independent owner. A peer copy
is SYCL memcpy through that Level Zero context with no application staging;
the capability query does not establish the driver's physical PCIe route.
The measurement must not call this a measured PCIe link rate without additional
route evidence. No peer atomics or persistent polling kernel is used.

- **Copy cases:** 10,240 B (10 KiB hidden vector), 65,536 B (64 KiB),
  1,048,576 B (1 MiB) and 16,777,216 B (16 MiB), A→B and B→A. Each case has
  20 repetitions with a new source byte pattern and a full destination check
  after *every* repetition. Report exact bytes, wall latency and decimal GB/s.
- **Peer selection:** only if both access queries return true. Unsupported
  access runs the pinned bounce cases only. Query/copy errors fail and latch;
  they never trigger a retry through another path. Even with access, run a
  host-bounce control: source D2H into the shared-context pinned slab, completed
  before destination H2D. No CPU memcpy is required between separate slabs
  because the one owner/context owns this slab for both queues.
- **Exchange:** B's FP32 vector → A's remote buffer → A's FP32 A+B kernel →
  B's mirror. Exactly 60 dependent rounds per sample and five samples per
  available mode. A's new result is its next-round input; B's fixed increment
  changes between samples. Both final copies are compared byte-for-byte with
  the CPU's 60 sequential additions. The B mirror readback verifies the return
  leg. No allocation/readback occurs inside the timed 60-round sequence.
- **Scope:** this is one reduction/broadcast primitive, not a complete layer,
  routing check or model token. The real model has 48 layers, with at least two
  communication phases/layer for conventional TP. The 60 count is the requested
  stress workload. No server, model payload, prompt, KV or decoding is involved.

All copy and compute submissions enter through the owner. `Device`'s global
dependency chain covers both queues, and each transfer/combine completion is
explicitly waited before dependent work. This intentionally measures a serial
round trip including host issue/wait overhead, not a captured or overlapping
implementation. There is one compute-capable queue per card and no inference
kernel competing with the copy. A later graph/event-only lowering needs its
own changed-input proof and measurement.

There is no discarded warmup: the first exchange sample can include JIT;
all five samples, min/median/max and raw events remain. Median is descriptive
only, not a fresh-owner speed verdict. Small CPU yield polling replaces the
packet5 backend's one-millisecond sleep; it is bounded by a five-second event
deadline. Polling is on the host, not a peer-memory device kernel.

Per-event timestamps are local; the receipt sums **durations** but never
subtracts clocks across cards. Zero, reversed or unavailable profiling intervals
invalidate that sample's event total, not its wall measurement. Copy GB/s counts
one delivered payload; bounce link traffic is twice that size. Exchange reports
the measured whole 60-round wall milliseconds, not a wire GB/s or a modeled
full-token time. First samples and failed/partial runs are retained.

## Ownership, admission and faults

[owner-source.json](owner-source.json) pins the existing stage1 owner and
packet4's completed-event retirement implementation to Git blobs and SHA256s.
The validator extracts them only under ignored `build/owner/`; shared sources
and sibling receipts remain untouched. Completed events are retired between
samples; graphs/allocations/queues remain alive. No event is retired with work
pending, and old IDs become foreign. The final protocol is quiesce → drain →
release graph leases and allocations → idle marker → release events → both
queues → SYCL wrapper and native Level Zero context. A failed teardown retains
ownership for the coordinator and cannot return a success receipt.

Requested user allocations (runtime/driver/JIT overhead is additional and unknown):

| Class | Bytes |
| --- | ---: |
| A: largest payload + remote + result | 16,797,696 |
| B: largest payload + mirror | 16,787,456 |
| Two pinned slabs, shared context | 33,554,432 |
| Total explicit allocations | 67,139,584 |

The [watcher](device_window.py) follows packet5's journal cursor, specific fault
signatures, bounded admission and single-child protocol. It records source/build
identity, PID, boot, cards, relevant runtime environment, host meminfo and raw
kernel lines. Any new fault, lost journal access, timeout, signal, exactness
failure or unsafe receipt writes output `STOP` and **`build/FAULT.json`**. A
subsequent invocation refuses while that latch exists. Review/preserve fault
evidence before any separately authorized recovery; do not delete it as scratch.

Stop sends one SIGTERM to the captured PID. The child checks stop/deadline before
allocation and submission, drains cooperatively and saves partial rows. There
is no hard kill, retry, server restart, driver reset or reboot. The 120 seconds
bound admission, not an uninterruptible driver call: an unsafe owner can remain
alive under the watcher for coordinator recovery. The watcher continues saving
journal evidence and includes five seconds of post-exit observation. External
idle/health verification remains required after clean exit. This packet never
claims that its authorization flag resolves the host halt or card admission.

## CPU checks and reconstruction

[build-receipt.json](build-receipt.json) records compiler commands and hashes,
CPU output, compile/link status and scratch cleanup. Native code is never invoked,
including for help/version/enumeration. `readelf` checks the host executable has
no SYCL/Level Zero/OpenCL/UR linkage before running it.

The shared [case code](cases.hpp) runs through CPU memory mocks: **24 copy cases,
480 changing payloads, three exchange cases and 900 rounds per CPU process**,
covering peer-supported plus unsupported dispatch. Two fresh host processes
produce the same test verdict. This proves mock/control arithmetic and checks
every returned byte; it does not execute the native backend or prove GPU parity.
Tests also check stop-before-allocation, pending-buffer lifetime, event retirement,
strict teardown and a fixed-order regrouping counterexample. Python tests reject
missing/duplicate cases, bad timing/units, incomplete exactness, missing event
coverage and unsafe teardown, and mock fault/deadline/journal loss behavior with
one launch, one stop signal and a persistent latch. No test launches a real child.

```bash
P=experiments/own-xpu-runtime/stage2/packet12-peer
nice -n 19 env OMP_NUM_THREADS=2 python3 -B "$P/validate.py"
```

This uses installed icpx 2026.0.0, `-fsycl`, strict math, and **two** build jobs.
It downloads nothing. By default it removes only its own newly created
`build/owner/` and `build/compile/` scratch. Existing run/latch directories are
preserved and an existing owned build refuses overwrite. Source extraction is
from pinned local Git objects. The first compile found an unsupported
`sycl::exception_list.empty()` call; using its supported `size()` fixed it.
No GPU failure occurred, because no native binary ran.

## Coordinator command — cards 2 and 3, not executed here

Prerequisites: resolve current host halt if applicable, verify both physical
UUID/index mappings and exclusive cards 2 and 3, fresh health and memory
admission, and preserve any earlier receipt/latch. The prior one-card windows
do not authorize this two-card window. No masked selector environment is allowed.
Recreate the compiled artifacts on CPU, then run one separately admitted window:

```bash
P=experiments/own-xpu-runtime/stage2/packet12-peer
nice -n 19 env OMP_NUM_THREADS=2 python3 -B "$P/validate.py" --keep-build
source /opt/intel/oneapi/setvars.sh
nice -n 19 env OMP_NUM_THREADS=2 python3 -B "$P/device_window.py" --authorized-device-window --cards 2 3 --seconds 120 --output "$P/build/cards2-3-peer"
```

The device command is provided for the coordinator, not run by CPU preparation.
It launches one native process and writes `native.json`, `window.json`, kernel
and stdout logs, and, only on complete success, `receipt.json`. Copy those exact
receipts into a tracked, modest-size measurement directory before cleaning any
future device build. Two fresh admitted owners are required before a speed
verdict; a failed attempt is never automatically rerun. Do not delete sibling
scratch or fault evidence. [Closeout](CLOSEOUT.md) closes this preparation only;
the measurement and full-model quality gates remain open.
