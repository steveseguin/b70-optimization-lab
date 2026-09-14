# Streaming exact-output comparison candidate

2026-09-14. The old comparison client loads both complete tensor archives through
Torch, constructs finite/difference temporaries, and copies tensor bytes for
hashing. The inactive `scripts/compare-clip-streaming.py` instead verifies and
compares F32 archives in 64 KiB tensor reads using the standard library. It
keeps complete raw-byte equality as the acceptance rule and retains the old
execution-ID, successful history, saved graph, cache, sample-rate, and model
receipt checks. JSON files/headers are bounded to 1 MiB. This bounds individual
reads and tensor buffering; it is not a measured process-RSS claim.

The original `compare-clip.py`, its frozen encoder/compiler callers, and their
source pins are unchanged. The new candidate is not deployed. Graph changes
still need independent review; matching captured bytes and reported identity
alone do not attest the live runtime. A present fault stops normal comparison;
the explicit historical-evidence mode emits `passed-offline-evidence` or
`failed-offline-evidence`, never the `passed` required by existing live callers.
The fault is rechecked before returning a normal comparison result.

Equal blocks avoid per-sample diagnostics. Unequal blocks are decoded as exact
integer F32 units; the largest absolute difference is rounded once to F32,
nearest ties-to-even. Signed zeros fail the byte gate but have zero numerical
difference. Opposite finite extrema can produce an Infinity diagnostic, with
an additional exact hexadecimal F32 result. Native Torch diagnostic-mode
equivalence is unqualified; no new Torch import was attempted. The arithmetic
helper's seven tests and limitations are recorded in
[its note](f32-difference-cpu-01.md).

Additional acceptance restrictions are intentional and recorded in each report:
F32 only, nonempty tensors, rank at most16, contiguous complete archive ranges,
summary layout/finite flags checked, exact JSON booleans for deterministic
settings, and rejection of duplicate JSON keys or NaN/Infinity constants even
in diagnostic metadata. The last restriction can reject an otherwise finite
capture whose diagnostic standard deviation overflowed or was undefined.
Opened-file identity, header/range and content-hash rechecks reject observed
changes; this is not an adversarial filesystem snapshot or locking mechanism.

Validation used only `python3 -B -S`, regular saved files, and synthetic temporary
archives. Fifteen comparator tests passed, covering exact and signed-zero
comparisons, finite-overflow diagnostics, layout failure, both fault checks,
execution/cache/model/sample-rate gates, malformed/nonfinite/hash-mismatched
captures, strict JSON, changed files, cross-block mismatch offsets, bounded
reads, malformed tensor descriptors, and existing-output preservation. The
final receipt pins all imported source dependencies:
`data/streaming-comparison-cpu-02.json`. The initial14-test receipt is preserved
as `data/streaming-comparison-cpu-01.json`; its test source is superseded by the
additional descriptor-rejection cases, with comparator/dependencies unchanged.

Saved-run checks used the command pattern:

```text
python3 -B -S experiments/ltx25-b70/scripts/compare-clip-streaming.py baseline-01 CANDIDATE --offline-evidence --output REPORT
```

| Candidate | Report in `data/` | Observed result |
| --- | --- | --- |
| baseline-02 | streaming-comparison-baseline-02.json | All four outputs byte-exact, distinct execution IDs |
| resident-split-03 | streaming-comparison-resident-03.json | All four outputs byte-exact, distinct execution IDs |
| speed-oracle-marble | streaming-comparison-marble-negative-01.json | All four differ; expected negative, exit1 |

The marble capture is a different prompt, used solely as a deliberate mismatch
fixture. It is not an optimization regression. No media was generated, saved,
or deleted. Artifact hashes and frozen-caller hashes are collected in
`data/streaming-comparison-evidence-01.json`.

Outcome: source and saved-evidence correctness pass; deployment and generation
speed remain unqualified. This candidate removes the validator's native-runtime
dependency and full tensor loads. No scalar/native comparative timing or new
end-to-end throughput is claimed. The measured generation baseline remains
about6.4 seconds per25-frame clip at256x256,24fps, nativeBF16 and original8+3
steps. This does not satisfy the real-time goal.

Same boot `39a36df1-8b22-498e-b74a-28384839a024`; FAULT remains present. Known
server PID95931 is sleeping; stalled clients96119/102144 remain present with
their earlier SIGINT pending. No server action, reboot, GPU request, native
runtime import, power/swap/cache change or retry occurred.

Next: preserve frozen callers and prepare a separately pinned integration only
after reviewing this candidate's narrower metadata contract. When host recovery
and health permit actual execution, qualify raw parity and diagnostic behavior
before promoting any client replacement. Continue source work while GPU/native
requests remain held; do not interpret this gate improvement as model speed.
