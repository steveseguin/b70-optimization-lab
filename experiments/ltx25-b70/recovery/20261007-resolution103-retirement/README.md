# Packet103 duplicate retirement candidate

This tool has not been applied by its author. CPU controls use temporary synthetic
archives only. It never controls processes, calls an endpoint, or touches devices.
Its scope is exactly the thirty `resolution-full-20261007-timed-14` through
`timed-43` archives, retaining the corresponding first-suite `timed-04` through
`timed-13` archives. All other files, including summaries and previews, remain.

The coordinator chooses exclusive absolute control paths outside the experiment
artifact root. Commands are separate and require review between plan and apply:

```sh
python retire103.py plan --out /absolute/control/retirement-plan.json
python retire103.py apply --plan /absolute/control/retirement-plan.json \
  --sha256 PRINTED_PLAN_SHA256 --receipt /absolute/control/retirement-result.json
python retire103.py restore --plan /absolute/control/retirement-plan.json \
  --sha256 PRINTED_PLAN_SHA256 --receipt /absolute/control/restoration-result.json
```

Planning runs the unchanged, hash-checked verifier from sealed packet103. Its
timed verification reconstructs native repeats, candidate comparisons and all
forty timed emissions. Planning may inspect a completed, idle retained run;
applying requires the exact server identity's PID to be absent and the coordinator's
`controlled-reload-stop-intent.json` and `controlled-reload-stopped.json` in the
fixed `resolution103-closeout` folder. It checks the existing controlled-stop
schemas, identity, SIGINT intent, no hard kill and no fault. No additional device
probe is required by this deletion tool. Keep the closeout summary unchanged
between planning and application: it is an input, not this tool's output.

Apply reconstructs the entire plan again before writing its intent or deleting
anything. Each selected file must be a distinct regular inode with nlink1;
full-file SHA256 and size must equal its retained counterpart and the verified
proof's raw-file hash. Tensor equality alone is insufficient. The plan retains
per-tensor evidence, execution/prompt associations, fixture, full stat identity,
allocated blocks, and an exact restoration map. Source/proof drift refuses the
operation; never edit a reviewed plan to bypass a refusal.

Every operation writes an exclusive full-plan intent, then fsynced per-file
intent/completion events, then an exclusive final receipt. File removals use
no-follow parent traversal, immediate inode/stat rechecks and directory fsync.
The retained source and stopped identity are rechecked before each file. These
checks are not a filesystem lock or capacity reservation: run under the
coordinator's exclusive artifact ownership. Allocated-block totals are estimates
of reclaim, not a guarantee about shared extents or concurrent disk writers.

Restoration admits the actual destination filesystem with a50GiB remaining floor,
rounded archive sizes and16MiB bookkeeping allowance. It uses exclusive ordinary
copies, file/directory fsync and final hash/size/nlink checks. It refuses existing
destinations and never makes hardlinks or overwrites. Inode and ctime are new;
the original identities remain in the ledger. The keeper is a restoration source
on the same disk, not an independent backup. Keep it protected while files are
retired. The completed retirement receipt means **verified before retirement**;
the unchanged full verifier fails while raw paths are absent. A restore receipt
does not claim a new full proof; rerun the unchanged verifier separately.

Any partial failure preserves intent, event journal, partial files and an
incomplete receipt when the process can write one. There is no automatic retry,
rollback or partial-resume mode. A crash can occur between a file operation and
its completion event; reconcile the per-file intent and actual file bytes before
manual recovery. The ordinary restore command requires all thirty destinations
absent; partially completed deletion/restoration needs separately reviewed
recovery using the recorded map, never deletion of surviving evidence to force
this command to pass.

CPU verification:

```sh
PYTHONDONTWRITEBYTECODE=1 python test_retire103.py
```

The controls exercise actual synthetic30-file deletion/copy round trips,
whole-archive and proof-hash disagreements, source/stat drift, nlink/symlink/FIFO,
live-PID and fault refusal, exact restore mapping, low space, no overwrite,
durable exclusive control records, and partial I/O failure journals. The full
sealed verifier is deliberately not run against active research by these tests.
The low-level exact-file/stat/fsync pattern follows the preserved historical
`scripts/retire-verified-outputs-99.py`; its old throughput schema is not reused.
