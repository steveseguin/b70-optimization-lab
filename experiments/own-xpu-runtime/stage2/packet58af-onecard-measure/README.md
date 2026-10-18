# Packet58af — complete one-card measurement preparation

This private copy of packet58ae prepares one diagnostic device job. The final
authority for its CPU readiness is `READY-FOR-DEVICE.json`, written last.
No GPU result, measured overhead or speed improvement is claimed by preparation.
The 29.259764 tok/s packet58z record remains unchanged.

Arm 1 retains the publication split: host packing, foreground H2D and scatter
events, and the existing inclusive host drain. The analyzer never adds a host
wait to the device work already inside it.

Arm 2 records all 48 layers' logical zero-copy miss bytes and resident bytes
from the existing route readback. These are requested weight bytes, not a
hardware PCIe traffic counter. One rotating layer per generated token receives
four events: resident gate/up, miss gate/up, resident down, miss down. The
selected kernels execute the unchanged rows and reduction arithmetic in two
disjoint partitions on the same in-order queue. Other layers keep one launch
per expert site. No new token wait, route readback, weight copy, KV compression
or graph capture is introduced.

The partition is selected at command invocation, after preparation, using the
current published pointer table and the immutable cache address range. Each
subgroup belongs to one routed slot. Invalid routes execute exactly once in
the resident partition, retaining the original NaNs, status and sticky error.
The new expert translation unit is compiled and linked explicitly; retaining
the parent's expert object would leave the instrumentation disconnected.

| Field | Definition |
| --- | --- |
| `miss_kernel_ms` | Device-event service of the miss partitions, including their arithmetic. |
| `miss_stall_ms` | Serialized dependency delay from resident completion to miss completion, including the interlaunch gap. This is not pure hardware memory-stall cycles. |
| `resident_slot_compute_ms` | Device-event service of resident partitions. |
| `overlap_window_ms` | That resident service interval, available to a future transfer design. |
| `actual_concurrent_overlap_ms` | Zero: this diagnostic deliberately retains the in-order queue. |
| `no_op_partition_ms` | Raw event service when a partition has no routed slots; excluded from useful service. |

The report includes every layer's sample count, separate event endpoints and
interlaunch gaps. A sum of sampled layer means is labeled an estimate, never
an observed token time or a performance headline. Splitting changes scheduling;
these measurements screen feasibility and do not establish a transfer speedup.

There are no graph events. The memory note
`xpu-graph-events-cannot-be-profiled` is respected: ordinary kernel events are
read only after the existing token drain. Timestamp failures fail the run.

One model load runs A0 off, B0 publication, A1 off, B1 resident/miss, A2 off.
Every view uses all twelve fixed prompts, a 64-token cap and every-token
packet49 `iq3-p49-split32-v1` checks. All views retain tile16, production HC,
the 21,552,729,600-byte cache, overlapped maintenance and BF16 KV. Request
state resets and `cached_tokens=0` are required. Repetition is diagnostic,
not a cold-suite speed submission.

Off views disable queue profiling; on views enable it after a quiescent drain.
The bracket therefore includes enabling profiling, extra partition launches,
event retention/queries and buffered per-token formatting. Both on views must
have median matched-prompt decode duration overhead strictly below 2% against
both warm off controls. A1/A2 drift must be at most 2%. A0 must still be exact
but is excluded from the warm overhead comparison. Enabling costs are measured
against the dormant hooks in this same executable; this is not a benchmark of
the executable against packet58z. An overhead failure invalidates attribution.

The single unqueued proposal is
`ops/lane-queue/proposed-p58af-measure-A.txt`, relative to own-xpu-runtime.
It requires card 0, lane A, the whole host and the existing packet58ab hold.
Its total active budget is 900 seconds, including two K1 fixtures and two
90-second drain gaps. Deadline expiry sends one graceful termination request;
safe drainage may extend cleanup. There is no hard kill or automatic retry.

The preregistered decisions are in `readiness-policy.json` and `analyze.py`:

- Rank 2: reopen publication feasibility only if measured H2D/scatter service
  supports the 0.7386 ms saving budget. Adoption still needs a complete safe
  replacement at or below 0.4924 ms, including host and dependency costs.
- Rank 4: reopen a bounded sparse-transfer feasibility test only if the sum of
  sampled miss service clears the saving needed for 3% over 29.259764 tok/s.
  This optimistic screen includes unavoidable compute; a real candidate must
  measure more than 3% net gain with all costs and the same quality gates.
- Rank 5: keep packet58aa's M2 build closed until a complete verification
  cycle, including draft, rejection, feedback, misses and cache costs,
  supports more than 30.723 tok/s. This diagnostic cannot supply that entire
  cycle. Missing costs remain unknown.

The reader rechecks the completed job, build identity, clean device window,
oracle, request resets, full prompt coverage, token order, event partitions,
serial event order, layer coverage and byte/count consistency. A successful
diagnostic never becomes a submission or quality-promotion attestation.

CPU checks bind both new executables, exact parent relinks, partition byte
comparisons with GNU and Intel, production subgroup geometry, two miniature
five-view repeats, bad-oracle refusal, full-size synthetic startup/reset,
real native parsing, intercepted queue-to-native arguments, the shared
`ops/rehearse_entry.py --report` and temporary queue planning. Individual
receipts live in `evidence/`; missing or failed receipts prevent sealing.

Restore and compile with nice19, helper cores, Python -B and stdin closed:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet58af-onecard-measure/restore_sources.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet58af-onecard-measure/build_engine.py </dev/null
```

Every compiler/link turn uses `ops/compile_turn.py`. The build cap is 200 MB;
preparation stops below 25 GB root free. Compiles use a 4 GiB address-space
cap. The inherited synthetic full-size mock reserves large virtual ranges but
touches under 4 GiB; its measured RSS is retained. No model/full-shape payload
is read during this preparation.

`lineage/vendor58ae-manifest.json` records the copied parent file hashes. The unchanged
12.2 MB source archive under `lineage/vendor58z/lineage/` is intentional retained
rebuild evidence, with its SHA256 in `copy-manifest.json`. It restores ignored
sources without mutable sibling source imports. Two pristine checked kernel
templates are retained under `native/templates/`; `split_source.py` applies
the deterministic instrumentation only inside this packet. Frozen parent ELF
inputs stay hash-bound and are verified by exact relinks. New binaries are
ignored and rebuildable. Additional CPU argument/parser helpers copied from
packet58ab are pinned in `lineage/argument-helper-provenance.json`.
