# Discarded recursive draft probe

The opt-in diagnostic reuses the existing MTP layer to propose tokens two and
three positions ahead. This measures the acceptance needed to judge a future
four-stage pipeline. It does not execute a four-stage pipeline or publish any
recursive proposal to the target/controller/output stream.

Launch configuration (the existing LAN adapter passes these variables):

```text
OWNRT_DRAFT_DEPTH_PROBE=3
OWNRT_DRAFT_DEPTH_VERIFY=1
OWNRT_EARLY_RANK1=0
```

Probe depth accepts only `0`, `2`, or `3`; missing means off. Byte verification
accepts only `0` or `1` and requires an enabled probe. Fault injection and TP
are refused with this diagnostic. `OWNRT_EARLY_RANK1=0` is mandatory: rank 1
must not start its next half and overwrite the shared reverse hidden row while
the previous recursive diagnostic runs. The setter also copies the confirmed
reverse row into owned host storage before flushing deferred work. That copy
has the target's actual stream byte width (F32 or BF16), and its address stays
stable throughout the recursive passes. The default two-card engine is unchanged.
Enabling the probe reserves at most 32 MiB of extra GPU memory; the actual
allocation is recorded in `draft-depth-probe-config.json` and the arena census.
The coordinator must include that reserve before admitting a run.

The mechanism comes from the lab's [packet66 recursive probe](../../stage2/packet66-mtp-depth2-probe/README.md).
Normal MTP first produces d1. Its completion callback queues the probe, without
submitting work or draining a queue. At the next draft command or a quiescent
reset, redirect, dump or finish, the probe saves every mutable draft allocation,
feeds d1 and the draft's own BF16 hidden streams back to the MTP layer for d2,
and optionally repeats for d3. It restores all saved bytes, host position,
disabled state, reverse-hidden pointer, attention extent and prepared attention
commands. It never changes the target arithmetic or uses target F32 streams as
BF16 data. If recursive execution fails, the engine halts; it does not submit
automatic recovery copies after the error.

With byte verification enabled, each cycle reads the backup and restored
mutable allocations and compares every byte. The original target/prefill gates
and unchanged-output comparison are still required: these byte checks alone
do not qualify the inference engine against the independent reference.

One persistent trace is opened at the rank's **original** output directory:
`rank0/draft-depth-probe.jsonl` for the current rank-0 draft. It stays there
across resets and redirects, so per-request service cleanup cannot delete it.
Each row carries `request_output`, confirmed position/token, first-proposal
position, d1/d2/d3, measured extra-pass wall times, restoration verification,
snapshot size and diagnostic-only/discarded labels. The last proposal flushes
on the next reset/dump/finish; analyze after that boundary. Recursive work,
snapshot copies and verification perturb timing, so a probe-enabled suite is
not a speed record. `restore_ms` includes optional byte verification.

Analyze one request from the repository root:

```bash
python3 -B experiments/own-xpu-runtime/engine/tools/analyze_draft_depth.py \
  --prompt-ids /path/to/prompt-token-ids.json \
  --native-result /path/to/native-result.json \
  --probes /path/to/original/rank0/draft-depth-probe.jsonl \
  --request-output /path/to/request/rank0 \
  --require-verified --output /path/to/new-analysis.json
```

The prompt file is the full JSON array of input token IDs. The native result
contains the verified `tokens` and controller `draft_rows`. Optional
`--reference-result` requires exact output IDs against a baseline. When service
retention leaves only a result containing `tokens`, use `--allow-output-only`;
that explicitly labels the weaker controller linkage and requires every
generated token position to have one probe row. Both forms bind the prefix by
absolute position and confirmed input token; the full input artifact hashes
are retained in the analysis. Do not combine traces from different requests.

The analyzer reports conditional acceptance: d2 is eligible only when d1
matches; d3 only when both d1 and d2 match. End-of-output censorship, rejected
prefixes and unavailable proposals are separate counts. It refuses duplicate,
missing or shifted positions, mismatched prefix/controller tokens, malformed
timings and missing byte verification when required. It makes no throughput
projection and does not equate internal engine parity with CPU-reference parity.

CPU checks:

```bash
python3 -B -m unittest discover -s experiments/own-xpu-runtime/engine/tools \
  -p test_analyze_draft_depth.py -v
g++ -std=gnu++20 -O0 -fsyntax-only -DOWN_RT_HOST_ONLY \
  -I experiments/own-xpu-runtime/engine/src \
  experiments/own-xpu-runtime/engine/src/gsq-rco-iq3s/dense-packed-block/engine/build/source/entry.cpp
```

The tests cover conditional counts, EOS/cap censorship, incomplete lookahead,
missing/duplicate/shifted rows, prefix/controller mismatches, explicit output-only
alignment, and the restoration-verification requirement. Syntax checking is
not a native runtime validation; the coordinator owns that next gate.
