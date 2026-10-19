# Packet162b — diagnostic device-speed preparation

The owner reopened preparation on October 19 to settle device speed before
spending more work on NaN parity. The old CPU closeout remains unchanged.
This packet runs no model and cannot qualify model outputs or promote speed.

The standalone SYCL binary builds and its CPU preparation probe passes. Seven
analyzer/report tests and six parser/refusal tests pass. Synthetic and real-row
CPU native comparisons match every tested final output/status byte, including
NaN inputs and invalid/tail routes. The earlier auxiliary NaN-chain failures
remain unresolved. **Device speed and device output equality are unmeasured.**

## Experiment

Use physical card 2, lane B, PCI `0000:43:00.0`, in the shared reservation and
drain protocol. Compare bundle8 E1 `p90exp::Kernel<IQ2_S,2560,64,false,true>`
with the private 11-bit decoder, retaining WG64/SG32/V8 and the original
arithmetic. `micro_candidate.hpp` differs from the retained candidate only by
forcing the row-stride expression to constant evaluation; the initial SYCL
compile otherwise reached a throwing layout helper. Both the source and three
failed build logs are retained. The production header in the checked packet131
include tree is byte-identical to packet136's E1 source. The complete 45-file
include closure now lives under `native-pinned/`; only absolute include and
source-location paths were rewritten. Original and private digests are in
`native-provenance.json`; compiler flags and active dependency hashes are in
the build receipt. The earlier cross-packet pin refusal is retained under
`evidence/micro-prep/attempts/` and is superseded by the private build.

Each test has 640 rows, K2560, ten distinct experts and independent gate/up
streams. The CPU preparation reads real admitted GGUF rows from layers 0 and
24: experts 0–9 and `(37*i+19)%512`, respectively. These are fixed representative
expert sets, not claims about a captured routing trace. Selected IDs are
mapped to compact slots 0–9 in both arms; the native bound keeps experts=512.
Only selected rows are allocated. Each shape has 10,752,000 control bytes and
11,264,000 candidate bytes; the candidate growth is 512,000 bytes. Both shape
inputs together read 20,992,000 raw GGUF bytes. No full model table is built.

For each shape and each of two finite input seeds, run 200 complete A/B pairs
in A/B/A/B order: **200 timed events per arm per stratum**, 1,600 events total.
Record raw device start/end timestamps. No elapsed-time deadline decides
whether data are correct. Before timing, compare all 25,684 output/status/error
bytes, including invalid expert 512 and a partial row range. A separate untimed
fixture reports signed zeros, subnormals, infinities and NaN payloads. It cannot
veto or silently qualify the finite diagnostic. Kernel initialization is not a
model warm-prompt measurement. The tiny selected bank may have different cache
residency from a full model; this is explicitly a repeated kernel diagnostic.

Offline analysis uses median(candidate device duration) / median(production
device duration) separately for all four shape/input strata. All must be
**≤0.85**, and all finite byte checks must match, to report
`reopen: NaN parity + full build`. That verdict calls for fixing NaN parity and
passing full-build prerequisites; it does not authorize adoption or assert
that those prerequisites passed. Any ratio above 0.85 writes the final
DO-NOT-REPEAT row after graceful drain/release. Missing, duplicate, malformed,
out-of-order or incomplete streams fail analysis. CPU streams never count as
device speed. No final speed decision or DNR row has been written yet.

## Safety and admission

Fresh proposal: `ops/lane-queue/proposed-p162-micro-B.txt`.
Job: `packet162b-enum11-diagnostic-B`.
Output: `evidence/enum11-diagnostic-B1/` (must not exist).
The expected device window is at most five minutes; the cooperative watchdog
is 1,200 seconds, four times that expectation. No retry, model server or service
restoration. Shared fault supervision, single-card FD census, reservation,
client admission and graceful draining are retained from the packet102 runner.
The device disk floor is 25 GB; the queue separately reserves 32 MiB for logs.
CPU prep uses nice 19, cores 8–15/24–31, Python `-B`, stdin `/dev/null`, a 4 GiB
address-space cap and the shared compiler turn. GGUF extraction checks active
packet58 units before every expert read; the running census was left untouched.
Device allocations are below 32 MB per shape. The inherited 2 GiB supervision
budget and 8 GiB host reserve remain conservative bounds, not power/settings.

## Readiness blocker

The exact device ELF and future argv pass the shared sandboxed CPU preparation
probe, exiting before the first device API. The probe substitutes synthetic
rows, since that sandbox intentionally cannot read weights. The real selected
rows separately pass the native CPU implementation and analyzer checks.
Malformed rank/repeat/options and a truncated row file are rejected.

The required unmodified `ops/rehearse_entry.py --report` was run. Its native
loader, preparation, storage and deadline checks pass. Gate identity has zero
refusals; its one warning is the intentional packet58 unit glob in the CPU
read guard. Its **report stage fails because `report_probe` only accepts
model-screen and one-card model entries**, not standalone `run_micro.py`
entries. Both smoke and bracket adapters reject at its explicit unsupported
entry check. Shared ops are frozen in this brief, so that tool was not edited
and its failed result is not relabeled as a pass.

The real packet `report_completed` path is tested independently, including
writing analysis and the negative-result row in a temporary fixture tree.
Temporary-copy lanequeue planning passes. Nevertheless the final readiness
marker remains **false** for the required shared report incompatibility.
Nothing is queued, and the runner refuses device execution while it is false.
A shared micro-report adapter (outside this brief's frozen scope) is the
remaining handoff requirement; no NaN repair or model build was substituted.

## Reproduction

From the repository root, prefix each command with
`nice -n 19 taskset -c 8-15,24-31`, use Python `-B` and redirect stdin from
`/dev/null`:

- `python3 -B experiments/own-xpu-runtime/stage2/packet162-iq2-lookup/build_micro.py`
- `python3 -B experiments/own-xpu-runtime/stage2/packet162-iq2-lookup/prepare_micro.py`
  (fresh `build/micro-inputs` only; no active packet58 unit).
- `python3 -B experiments/own-xpu-runtime/stage2/packet162-iq2-lookup/validate_native.py`
  (regenerates real/synthetic CPU streams and the exact-argv probe cases).
- `python3 -B experiments/own-xpu-runtime/stage2/packet162-iq2-lookup/test_micro.py`
  (requires the saved synthetic/real CPU streams).
- The proposal's exact native argv with `build/micro-host` in place of
  `build/micro-device` regenerates the real CPU stream. Use rows-file `synthetic`
  and shape `synthetic` for its companion fixture.
- `python3 -B experiments/own-xpu-runtime/ops/rehearse_entry.py experiments/own-xpu-runtime/ops/lane-queue/proposed-p162-micro-B.txt --report --json`

Run `seal_micro.py` last to repeat the entry/report and temporary-plan checks
and write the final readiness marker. It preserves any older marker in the
attempt history and leaves readiness false when the shared report fails.

All receipts are in [evidence/micro-prep](evidence/micro-prep). The frozen CPU
closeout, raw-chain failures, integer proofs and old candidates remain intact.
