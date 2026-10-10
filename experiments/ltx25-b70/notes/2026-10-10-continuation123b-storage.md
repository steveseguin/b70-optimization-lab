# Packet 123b: count only this run's disk use

Packet 123b fixes the storage refusal caused by other writers on the same disk.
It is CPU-prepared; the coordinator's live server and run directories were not
operated. The parent is unchanged sealed 123 at commit `bbcdbc8ce`, manifest
`db5ea277d381c8a77c1bae94cc4e25b1e22035a084a7e3a33b7d10e5d68b340d`.

The reported incident was at 2026-10-10 04:59:59 UTC: packet 121 refused with
HTTP 409 after the filesystem's free space fell by 3,212,566,528 bytes at chunk
419. The run itself held about 25 MB and chunks about 240 KB, with about 97.9 GB
free. These incident values are the coordinator's supplied evidence, not a new
inspection of the live run. The old subtraction charged every writer on the
single filesystem to the stream and could also hide growth when others deleted
files.

The new counter uses allocated blocks (`st_blocks * 512`) from the run directory
and its `output/stream123b-*`, `output/validation/stream123b-*` and
`requests/stream123b-*` entries. That includes qualification captures, hidden
preview temporaries, anchors, logs and receipts. It starts at their complete
retained allocation; there is no starting-free-space subtraction. Consumed
preview deletion reduces the total. The separate 50 GiB global reserve stays.

Each check holds a counter lock, reuses unchanged directory listings, re-stats
file allocations and updates cached totals by deltas. Re-statting is necessary
because logs can grow without changing their directory's timestamp. Traversal
and cache size are bounded, with refusal on more than 200,000 visited entries
or depth above 32. Symlinks, multiply linked files, special files and crossing a
filesystem refuse. Descriptor-relative traversal does not follow directory
symlinks. Concurrent writes are observed at the next check; this is a metadata
snapshot, not a quota or a transactional preallocation guarantee. Per-check
cost still grows with retained file count; no speed benefit is claimed.

`LTX_RUN_WRITE_ALLOWANCE_GIB=N` accepts integer GiB 1 through 64, default 3.
The launcher uses it for startup headroom and passes it explicitly to the
server. Runtime freezes it, writes `stream-launch-options.json`, and includes
`run_write_allowance_bytes` in status, qualification, chunk, decode and preview
receipts. The client expects 3 by default or the explicit
`--expect-run-write-allowance-gib N`; both wrappers use the same environment
option. A mismatch refuses. Raw capture counts and size bounds stay unchanged.
HTTP 409 storage refusal still stops the client with exit 15; preview failure
still exits 7 with one bounded status observation and no request retry.

The namespace follows 116b/118b: packet id is string `"123b"`, names
`stream123b-`, comparison mode `stream-candidate-123b-v1`, clip bases
12320000/12321000, unit `ltx123b-stream-server-20261010`, and
`launch-123b.sh` / `stream/start-client-123b.sh`. Wire schemas and latch names
stay as in 123. All 220 numerical identities and 3,960 fixed qualification
graphs are tested against 123 after only namespace/clip-index normalization.
The auxiliary residency helper and its already-transformed native sources,
atomic preview publication, native arithmetic and quality gates are inherited.

Packet: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-123b`.
Manifest: `5bdc0956f69259a99ca82849280e73b8bd2a80e28ff421ce5d61122e8a74d433`.
The [build receipt](../data/resume-20261008/continuation123b-build.json) records
final counts, command/log identities and recursive verification. The
[contract](../recovery/20261010-continuation123b-stream/CONTRACT.md) and
[launch reference](../recovery/20261010-continuation123b-stream/LAUNCH.md)
state the precise allowance scope and unchanged positional grammar.

All Python commands use `/home/steve/.venvs/ltx25-baseline/bin/python -B`.
Recovery tests use guarded children and at most four OpenMP/MKL threads;
client tests use audited synthetic loopback fixtures that reject port 8188 and
device opens. Their shutdown is cooperative, with no process signals. No model
server, GPU work, launch, real preflight, systemd/unit operation, port 8188
connection, render-device open, existing-run write, live-client write or host
setting change was performed. No device qualification or speed claim follows.

## CPU validation

Validated **592 recovery cases, 1,238 client checks and 10 mocked preflight
cases**. Counts exclude duplicate rechecks. The complete recovery discovery
ran all 592 cases: 589 passed immediately. Three copied fixtures needed changes:
the parent expectation still said 122, the walk-mode options dictionary lacked
the new allowance, and a mock deployed directory omitted `run_storage.py`.
The corrected parent module passed 5/5, the walk-mode case passed 1/1, and the
entire transient-budget module passed 28/28. No sealed production source changed
for these corrections. Earlier pre-seal development failures are retained too.

All 21 historical/new client suites were run. Four old wrapper assertions
(119–122) predated coordinator commit `e564dfe12`, which added client
`reset-failed` lines. Tests now recognize that existing own-client line and
still require `Restart=no` and no stop/restart command. The four full corrected
modules pass 70/70, 101/101, 112/112 and 138/138. No wrapper was changed or run.
The new 123b client suites pass 205 contract checks and 38 synthetic HTTP checks,
including a nondefault 8 GiB allowance, expectation refusal, HTTP409/exit15 and
preview500/exit7. The real integration class also passed a separate CPU harness
with 8 GiB recorded in nine qualification and two stream receipts.

The source commit is `af43e4e73`; the follow-up validation commit binds the logs,
fixture corrections and final receipt. Recursive verification covers 2,064 files
and their parent chain. Parent 123's manifest and author tree are unchanged;
11 selected residency, native-arithmetic and atomic-preview files are identical.
There are no `__pycache__` directories or `.pyc` files in the new author or packet
trees. Both shell wrappers pass syntax checking without execution.

Commands used (CPU only, output redirected to the build receipt's logs):

```text
/home/steve/.venvs/ltx25-baseline/bin/python -B recovery/20261010-continuation123b-stream/run_tests_123b.py
/home/steve/.venvs/ltx25-baseline/bin/python -B recovery/20261010-continuation123b-stream/run_client_suites_123b.py
/home/steve/.venvs/ltx25-baseline/bin/python -B recovery/20261010-continuation123b-stream/runtime_packet.py --inspect-assembly
/home/steve/.venvs/ltx25-baseline/bin/python -B recovery/20261010-continuation123b-stream/runtime_packet.py --build --input-inventory-sha256 ab9c909e58bf10c7b77d67902c740190fcf770c8e5b0ad63a5891b8e8dffd1a1
/home/steve/.venvs/ltx25-baseline/bin/python -B recovery/20261010-continuation123b-stream/runtime_packet.py --verify-manifest-sha256 5bdc0956f69259a99ca82849280e73b8bd2a80e28ff421ce5d61122e8a74d433
```

Paths in this command list are relative to `experiments/ltx25-b70`.
Build/verification invoked the same builder functions directly with these
arguments; they never executed the launcher's live `--check-only` mode.
The client batch writer uses exclusive log creation and refuses to overwrite
an earlier suite log. The immutable packet builder likewise requires a new
destination; do not rebuild over this seal.
