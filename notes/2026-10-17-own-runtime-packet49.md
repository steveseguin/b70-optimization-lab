# Packet 49: split32 QSA integration and production GEMV reconciliation

CPU preparation is complete and sealed. No device program ran in this task.
The coordinator owns every device window. The old packet45 SPEED6 record,
39.422 tok/s (`cmv9wjmtj013gle01v8k1yg4v`), remains unchanged.

## Registered scope

Derive a separate `experiments/own-xpu-runtime/stage2/packet49-integrate/`
from the packet45 SPEED6 snapshot at `34c62b433`. The current packet45 tree
also contains later SPEED7 and diagnostic changes, so it is not the baseline.
Keep 23/25 target layers, draft rank 1, capacity 4096, write-set snapshots,
the 30 GiB arena cap, reserve policy, and device host-core placement.
Change QSA decode attention to packet47 split32 for both M=1 and M=2.
The changed reduction tree gets a separate full-model CPU oracle; old output
differences are informational and the old oracle is never overwritten.
The exact SPEED6 non-QSA dispatch is also pinned. Fresh K2 results are retained
as measurements and a separate recommendation; a different timing winner does
not silently change this packet's unrelated production kernels. The pinned
choices still need fresh K2 exactness coverage before model windows can run.

Packet48 candidates require production reconciliation before adoption.
The source audit finds matching shapes and quantization classes. Ordinary GDN
layer4 uses IQ2_S gate/up, IQ4_NL down, and Q6_K QKV/Z. Packet48's dense control
wrapper specializes away production P33's runtime routing path, so it is not
the same compiled production control. The primary expert controls use the
actual P39 kernels. Packet46 repeats 32 synthetic blocks per tensor and measures
complete layers with 10 warmups/200 pairs; packet48 changes row bytes and measures
isolated classes with 4 warmups/24 pairs. These are known confounders, not proof
of a single cause.

| Class | Packet46 production control, µs | Packet48 isolated control, µs | Difference |
| --- | ---: | ---: | ---: |
| IQ2 gate/up | 81.875 | 106.927 | +30.6% |
| IQ4 down | 91.875 | 93.542 | +1.8% |
| Q6 QKV | 100.105 | 63.490 | −36.6% |
| Q6 Z | 39.740 | 31.875 | −19.8% |

Down remains the strongest candidate, but the registered production-layer gate
is still missing. **No packet48 kernel is production-enabled in packet49.**
[Packet48b](../experiments/own-xpu-runtime/stage2/packet48b-production/)
prepares the matched full-layer comparison and per-class decision. Its unchanged
control calls the production engine; the candidate changes only the four
primary GEMV classes. No performance conclusion is inferred from compilation.
Packet46 launch fusion and packet47 ordered attention stay closed.

## CPU and storage constraints

All CPU builds/tests run at nice 19 on cores 4–15,20–31, using `python3 -B`.
At most one compiler, two CPU model jobs, and one composite mode run at once.
Only the durable oracle job may read the admitted IQ3 payload. No GPU, sudo,
power, swap, cache, host-memory-setting or unrelated-process changes occur.
Builds and outputs use `/home/steve/own-xpu-runtime-results/` with packet
symlinks. This is the same root filesystem, not extra disk capacity; initial
free space is about 22 GiB. Existing results, sealed packets and untracked
work remain untouched.

The oracle estimate before launch is **6–12 hours**, about eight hours centrally,
for twelve 128-token
outputs with two lean CPU workers (historical rate about 20 seconds per
consumed position, 2,386 suite positions plus a 214-position first-prompt repeat).
It must retain the fixture
steps needed by the chain, including 1–8 and 97–104. A static arithmetic
identity and separate completion receipt allow kernel windows to precede
oracle completion without silently changing their seal.

## Qualification boundary

The oracle launched at **2026-10-17 03:44:10 UTC** in the durable CPU-only
unit **`own-iq3-p49-oracle-20261017b.service`**, with restart disabled. Initial
completion estimate: **09:44–15:44 UTC**, central estimate about 11:33 UTC.
Outputs are under
`/home/steve/own-xpu-runtime-results/packet49-integrate/oracle/results/`.
The first attempt refused before reading model bytes because idle I/O priority
was absent. Its output is preserved in `oracle/attempt1-io-admission`; the
corrected one-off launch adds `ionice -c3` without changing sources or binary.
[Exact unit receipt](../experiments/own-xpu-runtime/stage2/packet49-integrate/oracle/unit-receipt.json).

The independent scalar gate passed **135,168 bitwise pre-gate values**, and
six CPU admission tests passed. Full-model completion and device parity are
still pending. The coordinator must check completion using:

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet49-integrate/oracle/oracle_job.py \
  status --require-complete
```

Exit zero binds the full manifest, binary, sources, token/fixture results,
fresh-process repeat and KD captures. `old-v-new.json` is produced only once
the new suite exists; it compares against retained old outputs informationally.

Build/CPU passes do not establish full-model device parity or speed.
The coordinator chain mirrors K0/K1a/K1b/K2/W0p/KD/W2m/WS/WSs plus
WS128x/WS128. Oracle-dependent windows fail closed while outputs are pending.
[The queue runbook](../experiments/own-xpu-runtime/stage2/packet49-integrate/WINDOW.md)
contains exact commands. Eleven queue tests cover topology, oracle barriers,
strict receipts, fault signatures, output boundaries and durable-unit admission.

The integrated bridge supports and tests M=1/M=2. The full engine retains
SPEED6's per-row attention submissions during verification; it does not acquire
new M=2 batching merely from supporting the bridge shape. The independent
[attention review](../experiments/own-xpu-runtime/stage2/packet49-integrate/REVIEW-QSA.md)
records this limit and found no blocking arithmetic or scratch defect.

The twelve-prompt, 128-token suite preserves the old record's scope. It does
not satisfy the separate 512-token publication gate, and no comparison to
Strata's different hardware is a matched performance result.

## CPU evidence and review

The GNU host, Intel device and GNU ASAN/UBSAN binaries compile successfully;
no device binary has been executed. Two fresh GNU processes each pass 88 integrated QSA checks,
216 linked-kernel cases and 218 non-GEMV fixtures with 3,427 adapter checks.
Six owner/lifetime suites pass. The miniature snapshot gate passes 31 cases
and 26 full-state/negative checks. Twelve sparse metadata plan/dispatch rows
pass without reading weights, covering both ranks and the draft path.
The current Python admission receipt passes 22 tests. The independent review
also passes 64 scoped metadata tests and resolves all five findings.

Two fresh sanitizer processes pass 176 QSA checks in total. The sanitizer
snapshot gate also passes 31 cases and 26 full-state/negative checks. Both
sanitizers must halt on errors; the gate enforces and records this policy.
The normal snapshot receipt was refreshed after that gate-source change.
The final seal binds 32 binary/artifact hashes and 425 source hashes and passes
an independent read-only verification:

`c95a6cdf423d4c059afda23a6b9a5a2372f16781d021b7f65749fad1fd7ce5bb`

[Seal receipt](../experiments/own-xpu-runtime/stage2/packet49-integrate/build-receipt.json),
[CPU build and verification commands](../experiments/own-xpu-runtime/stage2/packet49-integrate/CPU-BUILD.md).
The build tree uses about 1.9 GiB, CPU evidence about 11 MiB, and roughly
20 GiB remains free on root. The oracle unit is still active at handoff.

**Runnable now under coordinator admission:** K0 → K1a → K1b → K2 → W0p,
using the early-phase command in the runbook. Packet48b E1/E2 can also run
without the full-model oracle; T1/T2 follow their exactness gates. These share
card0 and must run serially. **Wait for the new oracle:** KD → W2m → WS →
WSs → WS128x → WS128. The queue and each model window both enforce completion.

The read-only build preparer was repaired before sealing: it checks admitted
inputs without writing through inherited fixture symlinks or invoking the
historical weight scanner. Focused review confirms all six missing inputs
refuse and predecessor files stay untouched. Only one compiler is allowed.
Historical copied helper tests are not a newly qualified test matrix; the
old long-suite helper assumes different scope/arithmetic and is not used as
packet49 admission. The authoritative paths are the new build, seal, oracle
and coordinator entry points.

[Independent review](../experiments/own-xpu-runtime/stage2/packet49-integrate/REVIEW-INDEPENDENT.md)
and [CPU preparation closeout](../experiments/own-xpu-runtime/stage2/packet49-integrate/CPU-PREPARATION-CLOSEOUT.md)
retain the exact scope, setup failures and remaining gates.

## Committed checkpoints

All checkpoints are on `main` and were pushed immediately:

- `e0628d6e8`: registration and preserved SPEED6 identity.
- `6d7b7274c`: serial coordinator chain and oracle barrier.
- `8bef9b696`: control reconciliation and queue admission.
- `dee051a11`: independent CPU oracle and arithmetic proof.
- `b234d2933`: durable oracle unit and live-state record.
- `c63232ab8`: sealed production-matched packet48b.
- `d6ade9f54`: split32 runtime integration and fresh CPU gates.

The final build/seal checkpoint carries this note, CURRENT, the three build
receipts, six fresh gate summaries, final seal and independent reviews.
