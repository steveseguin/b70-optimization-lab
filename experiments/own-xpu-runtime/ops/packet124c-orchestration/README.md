# Packet124c CPU preparation and coordinator handoff

The selection is exactly packet118 bundle7: packet103 plus packet109 fusion,
packet105b head split and packet114's fixed 80,128-row draft prefix. Evidence
is the original packet118 smoke and both matched composite brackets plus the
native identity chain. Prefix selection never uses benchmark text or timing.
No speed gain is attributed to this host-path repair.

`copy_bundle.py` uses `copytree(..., symlinks=True)`, excludes chain outputs,
and audits every symlink in packet103 and packet97. Nine dereferenced links
are restored, including `oracle -> ../packet49-integrate/oracle`. Existing
links are preserved. The two absent startup97e links are obsolete scratch;
they were not copied directories/files. The complete audit is
[inputs/symlink-audit.json](inputs/symlink-audit.json).

`argument_gate.py` retains all eleven actual window paths, 31 intercepted
native argv constructions and the real K2 receipt replay. It also requires:

- The queue's exact `oracle_ready()` subprocess fails on packet124b's real
  copied-directory tree with the reported static-binding error, and passes
  on packet124c without an adapter masking the bundle root.
- `queue_gate.py` runs the actual `queue_runner.run` loop through all eleven
  windows in disposable scratch: twelve real input preflights, six real
  pre-LATE oracle subprocesses, storage precheck, prefix prerequisites,
  retention checks and receipt validation. Synthetic successful receipts and
  five malformed/nonzero-exit checks per window use the actual validator.
- Fresh-chain resume prerequisites refuse unregistered imports. The inherited
  synthetic resume tests exercise exact copying, tampering and model-window
  exclusion. This preparation does not import old chain outputs.
- Restored links still have their exact targets and native binaries still
  match. All native launches are intercepted. Journal, scheduler context,
  elapsed gaps and generated device receipts are explicitly synthetic.

The frozen screen sealer rejects source paths resolving outside the repo.
`seal_view.py` keeps that restriction, snapshots eight read-only input files
locally and records original/snapshot hashes. The chain adapter verifies both
sides at every install. It uses the real bundle's oracle symlink directly;
it no longer substitutes an orchestration-local root for `shared_oracle.P`.

Prepare under `nice -n 19 taskset -c 8-15,24-31 python3 -B`, with stdin closed:

1. Bundle `cpu_prepare.py reuse_build.py cpu_gate.py prepare_chain.py full_shape.py startup103.py`.
2. Here: `seal_view.py`, then `prepare.py`.
3. `argument_gate.py`, `launch_limit_gate.py`, then `orchestrate.py`.
4. `final_audit.py`, then `verify_ready.py`.

Readiness requires the extended argument gate, source-bound tests, complete
submission replay, both drain scans, unchanged getrlimits, native identity,
matching composites and fresh output. A later read-only refresh runs only
`orchestrate.py --evidence-only` followed by `verify_ready.py`. CPU gates must
be regenerated if their bound sources change.

The proposed command is stored in `ready.json`. Only the coordinator launches
it after live admission. This task launches no chain, queue job, service or
GPU work. Fresh output:
`stage2/packet124c-record-bundle/build/device-cards01-a`.
No manual lane pause or retry loop is introduced; ordinary exclusive timing,
fault, teardown and memory checks remain required.

`prepare_submission.py --chain <path>` prepares a completed qualifying chain's
portable evidence. `submission.py` retains the complete CLI. No submission is
performed here. The inherited 128-token scope remains explicit;
`realistic_final_gate.passed=false`, with no strict512 claim.
