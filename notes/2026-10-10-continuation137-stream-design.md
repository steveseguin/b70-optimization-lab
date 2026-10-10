# Packet 137: exact CPU finiteness scanning

Packet 137 is a CPU-prepared successor to 135. It replaces the scalar Python
loop in two F32 validation wrappers with an optional bounded integer-bit scan.
The parent behavior remains the default. This does not claim to remove the
pooled odd-period difference: the [timeline audit](2026-10-10-continuation-residual-cycle.md)
locates that difference mainly in fresh text every fourth source chunk.

The new `LTX_F32_SCAN=bulk` choice uses byte slices, a 256-byte translation
table and integer AND over aligned 64 KiB blocks. An F32 exponent is 255 exactly
when byte 3's low seven bits and byte 2's high bit are all set. Byte lanes remain
aligned, and AND cannot carry between them. The scan returns the same boolean
for every immutable, aligned little-endian F32 byte string. Empty bytes retain
the parent's `all()` result. NaNs and infinities refuse; signed zero,
subnormals and all finite mantissas are preserved. The input is never modified.

The wrappers preserve the parent's type, alignment and nonfinite error text.
Every original invocation remains fresh: no hash, finite verdict, anchor,
tensor, ownership fact, source file, memory value or safety result is cached.
The module refuses changed scan constants. NativeBindings pins the helper's
source, imported module, function owners and code objects; its mode agrees
with both the runtime option and the anchor-file wrapper. A late environment
change cannot silently change an imported wrapper's mode.

The option is reported in status, qualification verdicts, receipts, decode
records and preview records. The 137 client requires matching expectations and
pins the inner plan, not the plan-envelope bytes. `parent` uses the unchanged
scalar predicate; namespace and explicit option reporting aside, it retains
135 behavior. `bulk` adds a run-name suffix so both forms cannot accidentally
share a result directory.

No model arithmetic, native operation order, tensor shape, placement, dtype,
sampler step, text policy, anchor dependency, snapshot, memory floor, reserve,
GC policy, storage allowance or source/owner gate is relaxed. All inherited
eager/graph/repeat qualification and full image/waveform/latent/anchor output
gates remain. The candidate 145-frame launch retains split36 text, cone graph,
native serial display on card 3, GC 10 idle maintenance, full snapshots and the
existing storage and signature caches. No server or client launch was run.

The [predicate screen](../experiments/ltx25-b70/data/resume-20261008/continuation137-analysis/finite-screen.json)
passed 262,235 assertions and measured 13.031439→0.390965 ms per 786,432-byte scan
over 51 alternating CPU trials. Six scans precede samplerA; eleven occur on the
prompt thread and one during chain-anchor publication. Their gross removable
CPU budget is **0.151686 s/chunk**, of which 0.075843 s precedes A. Four overlapped
precompute scans are excluded. Additional helper binding checks and changed
overlap can reduce the native gain. A rough no-new-wait prediction is **5.09 s
per 6 s new video**, about 2.9% below 5.242 s; this is not a benchmark result.

Files and reproduction:

- [Contract](../experiments/ltx25-b70/recovery/20261010-continuation137-stream/CONTRACT.md).
- [Launch instructions, text only](../experiments/ltx25-b70/recovery/20261010-continuation137-stream/LAUNCH.md).
- [CPU suite driver](../experiments/ltx25-b70/recovery/20261010-continuation137-stream/run_tests_137.py).
- [Runtime CPU comparison driver](../experiments/ltx25-b70/data/resume-20261008/continuation137-runtime-validation.py).
- [Recursive verifier](../experiments/ltx25-b70/data/resume-20261008/continuation137-verify-packet.py).

Preparation uses `nice -n19 env OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
PYTHONDONTWRITEBYTECODE=1 /home/steve/.venvs/ltx25-baseline/bin/python -B`.
Tests use owned scratch and CPU fakes with device/network guards. Runtime-fake
comparisons do not prove native output equality or speed. Native qualification
and matched measurements remain pending with the coordinator.

Development failures are retained under the test record's `rejected01`
directory. The first CPU run found a missing receipt-module import and a
strict option-schema omission; both were fixed before the final seal.
The initial split36 fake run correctly refused absent parent references.
The final CPU driver first makes the same synthetic reference fixture used
by the parent precedent, then compares production parent and bulk settings.
This fixture is not a native reference or a substitute for native qualification.
The separate verifier's first attempt refused an inherited read-only Git
source check; its guard now allows only the required Git read commands.
Only captured CPU harness/mock PIDs were interrupted during the rejected
attempt. No model process was signaled. The rejected new packet was preserved
as `prepared-continuation-stream-137-cpu-rejected01`; parent 135 was unchanged.

A separate source review found unchanged numerical model sources, decoder,
schedule, precompute and storage helpers, and all 220 inherited qualification
identities. Off mode retains parent computation but adds the new helper's
ownership and option checks, so it is not promised to be timing-identical.
The inherited plan's GC launch recommendation still says 60 seconds; the
explicit production command selects the permitted 10-second setting. Actual
server options and receipts, rather than that recommendation, identify the arm.

The first complete recovery run executed 1,096 tests: 1,088 passed, seven
failed and one errored. Six assertions still named older packets or parent
hashes; one expected option map omitted `f32_scan`; one fake deployed packet
omitted the new helper. The corrected fixtures retain the same strict
assertions, including all 3,960 qualification graphs, and compare directly
to sealed parent 135. These are unbundled test changes; the sealed runtime
manifest is unchanged. The entire recovery suite is rerun after correction.

Final client validation passed **7,780/7,780 checks across 49 suites**,
including packet 137's 162 contract and 508 integration checks. Its all-pins
screen checks 19 packets with 38 inner-plan assertions. The corrected recovery
fixtures passed a separate 73-test focused rerun. Sealed-import validation
passed 9 tests and imported all 69 bundled helper copies (37 component and
32 runtime copies), across the three preseal probe modes.

The final complete recovery rerun passed **1,096/1,096 tests in 1,108.546 s**.
CPU runtime validation passed three configurations, each with nine
qualification chunks and two streaming chunks: 22 synthetic-reference
comparisons and 11 direct production parent/bulk comparisons were exact.
All 10 mocked preflight tests passed. Native output and speed remain untested.
The repository link and manifest-path checks pass. The broad pinned-hash
check reports 231 pre-existing unrelated drifts and no missing targets; the
packet-specific pins all pass. Owned scratch is removed, including all 43
observed final client temporary roots; pre-existing other-packet scratch was
left alone.

Final [build receipt](../experiments/ltx25-b70/data/resume-20261008/continuation137-build.json):

- Packet: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-137`.
- Parent manifest: `4356482eae2f1d7ac95b17e6483379ceed0cc90ed488d46765803451980402c3`.
- Manifest: `18c80d25c2ba4992d8c6dff24779737a056a325389a84486d24da674ef7e463e`.
- Inner plan: `61e39067e333d6c392b6a76fbe8b6a962878ed95dc577fb684e10a2af05321a5`.
- Recursive verification: 2,352 bound files; 2,354 physical files including
  the manifest and completion marker; zero `__pycache__` or `.pyc` files.
- Status: sealed, CPU-validated, native-unqualified.
