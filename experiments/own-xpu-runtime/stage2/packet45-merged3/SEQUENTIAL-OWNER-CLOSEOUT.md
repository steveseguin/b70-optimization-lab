# Packet45 sequential-owner gate repair — closeout

<!-- campaign-closeout -->

## Question and identity

On October 14, 2026, the owner reported that the repaired packet45 binary passed
218 fixture checks and 216 p33-linked checks on each card pair, but K1a's host
window rejected its five safe teardown rows because packet44 expected four.
This follow-up ran only CPU programs on `steve-b70s`; the supplied device receipts
were read as JSON. Model identity remains the quantized compressed Unsloth
UD-IQ3_XXS lane, `iq3-p17-detmath-v2`, full BF16 caches. No model arithmetic,
C++ source, device build, or coordinator shell command changed.

## Outcome

Accepted host gate repair. The expected ordered owner namespaces are nongemv,
actual-adapter, small-gemv, gemv-k2 and p39. Each row must belong exclusively to
its expected owner, be complete with exit code zero, allow safe exit, and report
integer zero live bytes and in-flight work. Exactly one owner card is required.
Missing, extra, reordered, duplicate and mixed owners fail. K1a/K1b and K2 use
this check. Both supplied device receipts pass the repaired gate when replayed
read-only; this is not a fresh device qualification.

The complete CPU suite and reseal passed: **24 gate receipts, 41 build artifacts**,
115 wrapper tests, 79 fresh miniature cases and all six fresh real-model cases
(48 tokens and 2,304 layer fixtures exact). The six HC compiler arms passed
4,752 checks. All 12 capacity-fixture arms were rerun, followed by selection,
ASAN/UBSAN, owner/controller/mailbox, draft and cross-placement gates. The final
blocked-launch admission tests passed. Peak combined anonymous memory in the
six real cases was 7,964,266,496 bytes. No CPU model process remains from this run.

The exact unchanged `coordinator_windows.sh` was invoked in CPU rehearsal mode:

| Context | Draft rank | Passed windows |
|---|---:|---|
| 4,096 | 0 | 9/9: K0, K1a, K1b, K2, W0p, KD, W2m, WS, WSs |
| 4,096 | 1 | 9/9: K0, K1a, K1b, K2, W0p, KD, W2m, WS, WSs |
| 32,768 | 0 | 9/9: K0, K1a, K1b, K2, W0p, KD, W2m, WS, WSs |

The test intercepts only the shell launch prefix to call
`window.main(cpu_rehearsal=True)` with the coordinator's actual arguments.
Hardware admission is mocked; host fixture children, receipt gates, prerequisites,
summaries and retention run. K0 is explicitly a structural shim. K1/K2 use host
validation. K2 must fail device timing while passing its new exact event-structure
check. W/KD use private miniature inputs, with two 128-token suite prompts. These
are CPU correctness and orchestration checks, not model-suite or speed claims.

## What worked

The [sibling audit](SIBLING-AUDIT.md) records every checked constant and its verdict.
Besides the reported four-owner check, it found the same stale legacy K2 call,
a missing teardown check in current K2, a stale `93+66` fixture formula, a
validate-only p39 timing-class assumption, and an unused packet40 wrapper harness.
All are repaired. Current binary/child sets, fixture totals, capacity grids,
p33 counts, suite caps, draft geometry and seal counts agree with the merged
runtime. No active 170-fixture equality remains.

The earlier 78 mocked window combinations replaced both `run_fixtures` and
`fixture_receipt_gate`, plus prerequisite receipts. The admission tests stopped
at deliberately blocked launchers. Neither consumed a real five-owner receipt.
Now the wrapper suite runs the exact three coordinator chains; the seal requires
their source/binary-bound matrix and retained archive in both wrapper receipts.
Fourteen new mutation/regression tests cover named ownership and K2 structural
omissions. A same-count wrong-owner substitution fails.

## What failed or remains uncertain

The first audit attempt exposed the validate-only p39 timing-class mismatch.
Its logs and scratch are preserved; after correcting the structural expectation,
the complete campaign was rerun. CPU K2 produces zero timing timestamps and
omits p39 timing rows by design; all 56 p39 validation scenarios are still required.
Device K2 continues to require all 65 timing classes. No speed requirement was
relaxed and no timestamps were invented.

Full device chains under the new host seal remain the coordinator's work.
The owner's successful K1a arithmetic run establishes the prior NaN repair's
device result, not the remaining merged windows. Changing the seal invalidates
old prerequisite identities even though every binary is unchanged. No device
program, discovery, `/dev/dri` access or sudo was used. The fault latch and all
48 incident-tree files were rehashed unchanged (49 protected files total).

## Evidence and patches

- [Gate implementation](fixture_support.py), [window integration](window.py),
  [K2 structure](k2_summary.py), [seal requirements](seal45.py).
- [Owner regression tests](test_fixture_owners.py), [K2 mutation tests](test_k2_structure.py),
  [coordinator CPU harness](coordinator_cpu_gate.py), [wrapper suite](wrapper_cpu_gate.py).
- [All constant verdicts](SIBLING-AUDIT.md), [chain receipt](coordinator-chain-gates.json),
  [final independent verification](evidence/sequential-owner-fix/qualification-summary.json),
  [read-only device replay](evidence/sequential-owner-fix/device-receipt-read-only-replay.json).
- [Reproduction commands](CPU-REPRO.md), [retention and restore instructions](ARTIFACT-RETENTION.md).
  Prior fixture matrices and seals retain their exact bytes; the current receipt
  contains only the fresh matrix. The failed audit attempt is also retained.

SHA256 after resealing (all values below are full hashes):

| Receipt | SHA256 |
|---|---|
| `build-receipt.json` | `12c9996d04bb95f1091a7cb58dd3cce1894821343746715cb902948200afd7b1` |
| `cpu-tests.json` | `a5320db99342fb85acdb4a3e23964224af998f29cd6ba2591bdb858aa955df47` |
| `window-seal-binding.json` | `24f8aa2857f0f45edd4af39c5021398a6aef62335981c9685f077b09b082d281` |

All 41 artifact hashes are unchanged from the input seal. Runtime hashes:

| Runtime | SHA256 |
|---|---|
| `gnu-host/own-rt-iq3` | `2416ec9c53c48d50b6fac450950162fdb480bac8c81c6f42d42177cb103d2ac4` |
| `icpx-host/own-rt-iq3` | `bfcff86532d952549e2ccf76e2143f7b3bc0057b714daa9468e355b162d65d33` |
| `asan/own-rt-iq3` | `2a601239a19694dcef3f3cc653ed537878301bab6c49fcc594add8490c957858` |
| `device/own-rt-iq3` | `50381aa1220a6c6e30a597e3c0fa72d93a97453cacd96fdd833d925ac703943e` |

All five device artifact hashes are explicitly listed in the final verification JSON.

## When to revisit

When the coordinator resumes authorized device qualification, use fresh chains
bound to the new seal. Any future fixture-owner or registry change must update
the named plan, source-contract tests and complete coordinator CPU rehearsal
before sealing. This closes the stale host-gate defect, not the runtime lane.
