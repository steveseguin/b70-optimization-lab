# Packet133: bundle8 prepared ahead of packet130 lane B

Prepared on `steve-b70s`, on `main`, with CPU work only. No GPU workload,
service, live queue, sudo command, power setting, host memory setting or reboot
was started or changed. No process was killed. The first `git pull --rebase`
refused unrelated dirty orchestration files; `git fetch origin` confirmed
HEAD and origin/main at `4cf1e0a73a78f73b1d24bf11df2b013b6952880b`.
Those unrelated edits were preserved.

The new [packet133 bundle](../experiments/own-xpu-runtime/stage2/packet133-record-bundle/README.md)
and [orchestration](../experiments/own-xpu-runtime/ops/packet133-orchestration/README.md)
copy frozen packet124c. Exactly two compositions are sealed: bundle7 control
and bundle7 plus packet130 suffix interleave. The public dimension
`suffix_schedule=production|interleave` maps to the unchanged native values
`production|layer-interleave`. All 182 parent symlinks survive, including the
packet49 oracle authority; `find -type l` comparison is retained in
[the copy audit](../experiments/own-xpu-runtime/ops/packet133-orchestration/inputs/symlink-audit.json).

The exact native delta is pinned to packet130 commit `e5328b753` and its copied
source hashes. Both compositions and the chain reuse packet130 v5's GNU/device
binaries byte-for-byte. Its source-bound head/controller/reset/protocol CPU
qualification is checked, not represented as newly run device evidence.
The packet133 GNU/Intel arithmetic fixture replays, full-size numerical
initialization, memory admission and all eleven startup paths per selection
run afresh. The copied new `ops/compile_turn.py` controls the local numerical
CPU fixture compilations. Native arithmetic remains `iq3-p49-split32-v1`, with
BF16 KV, target split 24/24 and the fixed 80,128-row draft prefix.

The memory plans differ only in their human-readable `view` label, which now
includes the scheduling dimension. The evidence reader compares every other
memory field exactly, including allocations, capacity, topology and margins;
it does not relax a memory limit. KD projects suffix scheduling to production
because it captures the draft without a resident target head. Packet131 is a
documented disabled slot, not a third composition.

## CPU validation

[Final audit](../experiments/own-xpu-runtime/ops/packet133-orchestration/cpu-final.json):

- **83 tests and 11 subtests pass**, including the complete submission CLI,
  portable synthetic-chain replay, payload/attestation checks, both selections,
  threshold boundaries, missing evidence, altered identities and strict gates.
- **22 real CPU startup paths**, both selections × all eleven windows.
- **11 actual Python window paths**, with **31 intercepted native argv lists**.
- The actual queue loop passes **12 input preflights and six oracle checks**,
  with malformed receipts, nonzero exits, unregistered resumes, old K2 code and
  the old broken oracle copy refused as expected.
- Both recursive drain scans pass. Four native-limit cases pass, covering
  smoke/composite/chain exec and refusal of an inherited finite address-space cap.
- The [lane-A proposal](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p133-v5-A.txt)
  passes planning on a disposable queue. It is **not queued**. Expected bracket
  duration is 12–20 minutes; the watchdog is 80 minutes (4× the upper estimate).
- Final logical build bytes: **256,067,510**, below 300 MB. Root free space at
  the audit: **39,201,013,760 bytes**, above 25 GB. Peak recorded CPU fixture
  memory was **1,250,344 KiB**, below the 8 GiB process cap.

Commands used nice19, CPUs 8–15/24–31, Python `-B`, `OMP_NUM_THREADS=2` and
stdin `/dev/null`. Caps were applied only by explicit CPU entry processes;
the native-limit gate ran without an inherited cap. Launch entries embed a
closed environment and need no caller-supplied library variables.

Preparation sequence:

```text
stage2/packet133-record-bundle/reuse_build.py
stage2/packet133-record-bundle/cpu_prepare.py cpu_gate.py prepare_chain.py full_shape.py startup103.py
ops/packet133-orchestration/seal_view.py
ops/packet133-orchestration/proposal_plan.py
ops/packet133-orchestration/prepare.py
ops/packet133-orchestration/argument_gate.py
ops/packet133-orchestration/launch_limit_gate.py
ops/packet133-orchestration/orchestrate.py
ops/packet133-orchestration/final_audit.py
```

An initial arithmetic fixture lookup selected the first historical prefix
rather than the fixed 80,128-row entry; it refused on the combined hash. The
lookup now uses the exact bundle7 key. An initial lane-A plan refused because
the frozen screen confines outputs to its own packet. The local screen copy
changes only the output root and frozen worker location, with a test enforcing
that two-change delta. The real lane-B reader initially refused the changed
memory `view` label; exact comparison of all allocation fields resolves that
label-only mismatch, with positive and negative tests. No GPU retries occurred.

## Readiness and the lane-B result that arrived during preparation

[ready.json](../experiments/own-xpu-runtime/ops/packet133-orchestration/ready.json)
records `cpu_preparation_ready=true` and **`ready=false`**. The chain directory
`stage2/packet133-record-bundle/build/device-cards01-a` is fresh and absent.
`verify_ready.py` refuses launch unless the composed candidate passes a
12 × 64 exact smoke and both complete v5 lanes qualify. Each lane requires
both candidate repeats to beat every control by at least 0.5%, control drift
at most 3%, exact oracle tokens, zero cached tokens, unchanged native identity,
reset/weight/allocation proofs, and identical per-prompt acceptance counts.
The all-window argument **and queue** gates are mandatory.

Packet130's B bracket finished while this CPU preparation was underway.
The new reader replays its artifact hashes, raw requests, output oracle,
incidents, boundaries, isolation and wrapper identities. It confirms exact
output, but **does not qualify the speed**:

| B bracket view | Class-balanced tok/s |
| --- | ---: |
| Control 1 | 58.1309578566 |
| Candidate 1 | 57.2286309900 |
| Control 2 | 58.1542433013 |
| Candidate 2 | 57.2816563399 |
| Control 3 | 58.1624039610 |

The slower candidate divided by the fastest control is **0.9839454199**,
or **−1.605458%**, below the required +0.5%. Control drift is 0.054095%.
This is read-only replay of packet130's existing run, not a packet133 device
measurement or a new headline. The [bound verdict](../experiments/own-xpu-runtime/ops/packet133-orchestration/evidence/lane-B-verdict.json)
retains its window, summary, selection and reader hashes. Lane A and the composed
smoke remain unrun. The proposal stays unqueued; the B failure cannot be
replaced by old bundle7 evidence or a lowered threshold.

The current record stays **58.223834 tok/s**, `cmvdx8urg0068rf01vvb32bcs`.
The submission tool is complete and its notes name that superseded record only
conditionally on a future qualifying faster chain. They retain the original
prefix preregistration, quantized-model identity and honest 128-token scope:
`realistic_final_gate.passed=false`, no strict512 claim. Nothing was submitted.

After evidence changes, the only remaining preparation operations are the
read-only evidence refresh (`orchestrate.py --evidence-only`) and readiness
verification. Current B evidence explicitly blocks the chain. A different
candidate or replacement run needs a new preregistered identity, not edits to
the frozen result. No launch is authorized by this note.
