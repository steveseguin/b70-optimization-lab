# Packet207 paired-projection authority

## Question and identity

Can the actual tiny Engine replace two independent GDN qkv/z projections with
prepared two-row projections while preserving row inputs, recurrent order and
all observable checkpoint state? This is an additive HOST_ONLY experiment based
on the frozen packet206 overlay. It does not enable full-model or device use.

Two different authorities are required. The lifecycle uses synthetic F32 weights
and the tiny four-layer Engine. A separate synthetic arithmetic fixture exercises
the same paired-operation ABI at production-shaped Q6_K K2560, qkv10240/z6144,
expanded variant6/split1. That fixture must compare against independently called
frozen p33 serial arithmetic; comparing the pair implementation with itself is
not authority. Neither proof establishes device equivalence or speed.

## Outcome

The second root-designated run, `host-proof-b`, passed. Its two Engine owners
completed32 requests,26SAVE and6RELEASE in total. All13 checkpoint snapshots
per owner match the serial control and packet206 external bytes, including all20
state blobs and tokens.bin. All108 candidate prefill endpoints match serial;
400 actual prepared paired projection sites replace800 original sites. Both
owners exited0 without SIGTERM or retained resources.

The separate same-binary ABI process passed both full-shape Q6 comparisons
against frozen p33 serial arithmetic, together with changed-row, changed-weight,
captured-metadata and admission-refusal controls. Its two synthetic Devices
drained with exit0. Ten parser-only refusals passed before owner output creation.
[The executed proof](evidence/host-proof.json) binds these results. Twelve
read-only checks passed afterward; they started no native processes.

## What worked

The unchanged [fixtures](fixtures.json) specify the same16 requests as packet206:
fresh/interleaved A/B, resume, append/repeat/fresh, odd and one-token prompts,
the31→32 pending-token/capacity boundary,33-token prompt and near-capacity prompt.
Two sequential owners use the same new binary, resident memory and context64:
serial control and chunk2 paired candidate. Each must finish16 requests with
13SAVE and3RELEASE. All20 checkpoint blobs, tokens.bin, token history/control
descriptors and generated sequences must match. Candidate prefill endpoints
must equal serial endpoints at the same published positions, and all13 saved
states must also match packet206's retained external bytes. Checkpoints are
restored only within their own new-binary owner; no cross-binary restore is used.

GDN layers0 and2 each require a retained row prefix, one prepared qkv pair and
one prepared z pair, then causal suffix/FFN row0 followed by row1. Other layers
keep their original per-row operations. The fixture contains100 chunks, so
actual issuance diagnostics establish400 paired projection sites, with
the corresponding original qkv/z sites skipped. A chunk flag or matching output
alone cannot establish that the new path executed. Diagnostics must identify
distinct row inputs/outputs and a shared weight binding. Mutation controls must
demonstrably detect wrong row binding and changed weights; counters alone are
not a speed measurement or hardware bandwidth proof.

## What failed or remains uncertain

The first designated run reached a successful full-shape Q6 ABI proof and all16
serial requests, then failed in the harness after the first candidate request
and SAVE. It read `owner/census.json` before Engine shutdown had published it.
This was a harness `FileNotFoundError`, not a numerical mismatch. One graceful
SIGTERM drained the candidate owner with exit0 and no retained resources. The
exact tested harness/fixtures/authority/build, root log and all609 closed files
are retained under
[before-final-census-join](lineage/before-final-census-join/retention.json), with
complete archive member readback and original-file rehash verification.

The bounded correction keeps schedule, issue, skip and alias checks on every
request, and defers the actual allocation-census join until successful close and
owner exit. Three CPU regressions use the retained real eight pair records and
final census, including absence before shutdown and incorrect-ID refusal.
The binary is unchanged. A fresh output requires an explicit new root-designated
run; no native retry occurs inside the harness.

The original packet206 intentional partial-chunk owner failure remains historical
evidence for its unchanged poison/drain policy. This packet does not repeat that
third owner and must not claim a newly executed whole-owner failure proof.
New paired ABI admission and mutation controls are separate bounded synthetic
checks; source review must verify that new exceptions still reach the poison
catch without serial retry or partial success publication.

The production model is heterogeneous. The recorded plan has36 GDN projection
pairs; layer2 qkv/z are Q8_0 (GGUF type8), while the chosen layer0 pair is Q6_K
(type14). This comes from the pinned packet181 input plan, not inference from
allocation sizes. The [production census](production-census.json) records sizes
and layouts separately. Unsupported types/layouts remain unqualified; a future
production integration must preserve an admitted original path rather than
treating every GDN matrix as Q6_K. The four retained production row regions total
37,896 bytes: HC mix5,120, HC injection8, qkv20,480 and z12,288.

Mini F32 end-to-end results cannot prove production Q6 end-to-end behavior.
Synthetic full-shape Q6 arithmetic cannot prove real model quality, expert cache
cadence, production cached FP32 conversions or asynchronous device ordering.
Host/LifetimeMock/MockDevice event provenance remains simulated. Weight-sharing
structure and issue counts do not establish a measured throughput improvement.

## Evidence and patches

[authority-inputs.json](authority-inputs.json) binds frozen parent evidence.
[host_probe.py](host_probe.py) defines the fresh-output, bounded CPU lifecycle;
its exact plan and retained results are separate from this authority note.
The parent [host proof](../packet206-host-engine-chunk/evidence/host-proof.json)
and [authority](../packet206-host-engine-chunk/AUTHORITY.md) retain the successful
serial/chunk state proof and intentional failure. Parent sources and states stay
unchanged. Build and arithmetic receipts bind the actual new ABI source,
independent reference source and compiled artifacts.

[raw-host-proof-index.json](evidence/raw-host-proof-index.json) inventories all
1,094 files and13,526,310 logical bytes of the successful B run.
[raw-host-proof.tar.gz](evidence/raw-host-proof.tar.gz) permanently retains those
research artifacts in1,171,008 bytes, including all26 tiny checkpoint snapshots,
per-request observations, pair issuance records, synthetic ABI result and parser
logs. It contains no compiled executable/object, model payload or credential
dump. Every archive member was read back and compared with its index and the
original file; originals remain untouched in `build/host-proof-b`. Failed A's
609 files are separately retained in its700,125-byte lineage archive, with the
exact tested sources and root log. Neither failed evidence nor failed sources
are replaced by B.

The read-only [authority checks](tests/test_host_authority.py) consume the B
archive/index, and [census timing regressions](tests/test_census_timing.py)
consume the failed A archive. Git retains both archives and inventories as
permanent experiment evidence. Verify each archive's SHA256 against its index,
then inspect in a fresh empty directory with
`tar -xzf evidence/raw-host-proof.tar.gz -C /fresh/empty/directory`.
Members are relative regular files, validated by the tests; do not extract over
an existing run. Rebuilding uses the separate pinned source/object closure.

## When to revisit

With these bounded numerical and Engine binding gates passed, review the remaining
production type/layout coverage, cache semantics and device execution boundary.
Any later performance experiment requires a separate exactness and run-identity
review; no estimate here is a measured candidate speed.
