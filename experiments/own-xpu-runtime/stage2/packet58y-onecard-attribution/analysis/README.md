# Evidence-only analysis

Run after the coordinator completes 58x smoke → 58x bracket → 58y in the same
continuous whole-host hold, from the repository root:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet58y-onecard-attribution/analysis/analyze.py </dev/null
```

This reads evidence and writes `analysis/report.json` and `analysis/report.md`.
It launches no process, device operation, model, service or queue action.
The CLI applies a 4 GiB address-space ceiling and requires the 25 GB root-free
floor. Missing receipts produce a pending report. Invalid evidence produces a
refusal in both formats, replacing any previous result. Both are non-passing.

The reader verifies the sealed runtime and readiness binding, the eight expected
predecessor receipts, their hashes, clean stages, build and boot identity,
chronology and stored pause identity. It rechecks the diagnostic window's full
file closure, shared packet49 oracle, every output token and every trace row.
The coordinator remains responsible for excluding intervening lane-A work;
stored receipts are not a complete host scheduler audit.

The primary split covers exactly the 99 intervals from output event 1 to 100
for each of twelve prompts. All decode rows and the cold first prompt are
retained separately. Rates are medians within classes, then across classes.
The report records endpoints, numerator, count and interval-minus-trace residual.
The native token clock excludes its final trace write; that residual retains
the extra time charged by the actual generated-token timestamps.

Six host/wait buckets are ranked by the optimistic gain if each entire bucket
vanished. A bound below +3% kills that isolated lever. A bound at or above +3%
only merits a causal test: it supplies no supported performance projection and
cannot pass the implementation or promotion gate. Decimal ratio comparisons
retain the exact +3% boundary. Host work overlaps device execution, so removal
bounds are not additive and are not predictions.

The reader also recomputes 58x's five views from raw exact-checked outputs.
It keeps the cold A0 view visible and uses 58x's preregistered A1/A2 controls
against B0/B1. More than 3% control drift makes that comparison inconclusive.
The measured conservative gain is compared with the same +3% priority gate.
Neither a single-process capacity screen nor this instrumented diagnostic is
a speed record. The differing allocation makes 58x unsuitable as a matched
instrumentation-overhead control.

Device-class durations and isolated miss stalls stay null: no valid device
timestamps or independent miss critical-path measurement exists. Counts and
logical bytes cannot establish that the miss path is still a top lever.

`test_analysis.py` uses only temporary synthetic receipts and the existing CPU
oracle fixture. It covers the complete analysis path, changed traces, missing
receipt coverage, exact boundary decisions, class balancing, unsafe paths,
pending evidence and replacement of stale successful Markdown after refusal.
Synthetic outputs are deleted by the tests and never become device evidence.

The analyzer was prepared after the READY milestone. Its separate directory is
outside the sealed runtime source set; it does not change the proposed binary
or the readiness marker. Only reading completed evidence remains.
