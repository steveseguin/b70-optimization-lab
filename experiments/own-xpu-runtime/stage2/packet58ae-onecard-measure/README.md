# Packet58ae: one-card measurement preparation — blocked

This is **incomplete CPU preparation**, not a ready device experiment.
The packet is vendored from packet58z's frozen source archive. Neither parent
nor any live queue was changed. The combined proposal must not be queued.
`entry.py` refuses device execution even if someone flips the saved readiness
boolean, because the Arm 2 capability is missing.

The implemented Arm 1 records host packing, H2D and scatter device events,
and time in the existing publication drain. Host wait includes the device
work; the analyzer never adds those overlapping durations together. Events
are read only after the existing token drain. There are no new token waits.

The partial Arm 2 records all 48 layers' routed hit/miss bytes from the existing
route readback. It retains two selected expert-site tail events from one
rotating layer per token, so all layers receive samples over each 64-token
request. These are **mixed-kernel event durations**. They are not independently
measured miss stalls, resident-slot compute or overlap windows. Those three
fields remain null. They cannot reopen packet147 rank 4 or the M2 verifier.

The reason is in the retained source: the pointer table selects host or device
weights inside the same gate/up and down kernels. A timestamp around a whole
kernel cannot separate its resident and miss subgroups. A correct follow-up
needs separately bounded slot timing or another validated attribution method,
plus its own output and overhead checks. This packet does not infer a stall
from miss bytes or subtract an unrelated resident timing.

## Intended device run

One load, one card (card 0), lane A, whole host, in packet58ab's existing hold:
A0 off, B0 Arm 1, A1 off, B1 Arm 2, A2 off. Each view uses the fixed twelve
prompts with a 64-token cap and checks every generated token against packet49
`iq3-p49-split32-v1`. Tile16, the 21,552,729,600-byte cache, overlapped maintenance,
BF16 KV, weights and arithmetic remain unchanged. The estimated complete job,
including two K1 fixtures and drain gaps, is at most 900 seconds; watchdogs
are 3,600 seconds. This estimate has not been validated on the device.

Off views use an unprofiled foreground queue. On views use a profiled foreground
queue, replaced only after the existing quiescent drain. The same owner,
context and model allocation remain. Thus the bracket includes queue-profiling
cost, retained events, timestamp reads and buffered log formatting. It does
not hide profiling overhead by leaving profiling enabled in the off controls.
No device run has established the required **strictly below 2%** overhead.

`analyze.py` is read-only. It revalidates the bound oracle and request evidence,
checks both on views against both warm off controls using matched-prompt
median duration ratios, and rejects overhead >=2% or warm-control drift >2%.
A0 must be exact but is excluded from the warm comparison. This is diagnostic
repetition, never headline performance. Missing evidence stays pending.

The preregistered rules are in `readiness-policy.json`. Arm 1 can reopen
sparse-publication feasibility only when measured transfer/scatter service
is large enough to cover the required 0.7386 ms saving. A complete replacement
still has to measure <=0.4924 ms, including host work, dependencies and waits.
Arm 2 cannot issue an optimization verdict without its missing measurements.
M2 additionally needs the full draft/cache/verification-cycle costs and the
30.723 tok/s threshold; this packet cannot supply those costs alone.

## CPU evidence and remaining work

- Both GNU host and Intel SYCL executables compile through `ops/compile_turn.py`.
- Exact relinks of the unchanged objects reproduce both frozen parent hashes.
- Two miniature five-view repeats preserve output tokens and every retained
  layer file. A corrupted oracle fails before B0 and drains cleanly.
- Analyzer failure cases cover overhead, drift, missing events/layers, invalid
  timestamps, overlapping host waits, unknown stalls and fail-closed admission.
- `ops/rehearse_entry.py --report` passes both native entries and both real
  report paths with no duplicate imported module names. Report fixtures are
  synthetic CPU evidence, not device validation.
- Pin guard and the temporary lane-A queue plan pass. The proposal is unqueued.

Remaining: implement the separate Arm 2 measurements; rerun complete native
startup/full-shape and real queue-to-native argument gates for this changed
engine; establish the off/on overhead and every-token device parity in the
approved hold. No inherited startup receipt is claimed for the new executable.

## Retention and restoration

`lineage/vendor58z/` is an unmodified, symlink-preserving source/configuration
copy. Historical device outputs and submission bundles were excluded. Its
12,203,538-byte `lineage/58x-build-source.tar.gz` is intentionally retained:
it binds the exact parent source archive and restores the ignored expanded
source trees. Its original SHA256 is in `copy-manifest.json`. It is needed to
rebuild without importing mutable sibling source. `lineage/supplemental/`
retains the small generated owner/backend source missing from that archive;
the original copy hashes are retained in `lineage/supplemental-copy.json`.
Hash-bound parent ELF objects remain immutable link inputs, independently
verified by the parent relinks. The new binaries are ignored and rebuildable.

CPU commands (no model/device execution):

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet58ae-onecard-measure/restore_sources.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet58ae-onecard-measure/build_engine.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet58ae-onecard-measure/cpu_gates.py reset </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet58ae-onecard-measure/analyze.py </dev/null
```

The last command prints pending when the completed combined run is absent.
`READY-FOR-DEVICE.json` is written last and reports `ready_for_device=false`.
