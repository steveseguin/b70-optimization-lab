# Packet 133b: sealed-launcher import repair

CPU-only packaging rebuild of sealed packet 133. The coordinator's original
rehearsal failed before device work. Packet 133 and all existing runs remain
unchanged. The coordinator retains control of the live service.

The failure log is preserved as
[check-only-133-original.log](../data/resume-20261008/continuation133b-tests/check-only-133-original.log).
`serve-encoder.py` imports `launch/encoder_runtime_common.py`, whose environment
check loads `resolution/components/cone_memory131.py` by absolute file path.
That module's text-shift branch imports `text_residency133` by name. Packet 133
had that helper in both `resolution/components/` and `source/scripts/`, but
neither directory was on the launcher's import path at that point. The launcher
adds the source paths much later. Author-tree CPU suites already had the helper
on their import path, so they could not expose the packaging defect.

133b additionally bundles the unchanged helper in `launch/`, alongside its
unchanged, hash-pinned `text-oracle133.json`. The oracle copy matters: Python
keeps the launch-directory helper in its module cache, and its adjacent-oracle
lookup must still succeed when the runtime later uses it. No tensor operation,
weight, precision, qualification id, numerical contract or safety latch changes.

The rebuild follows the 116b/118b/123b convention: string packet id `133b`,
`stream133b-` names, comparison mode `stream-candidate-133b-v1`, clip bases
13320000/13321000, unit `ltx133b-stream-server-20261010`, `launch-133b.sh`,
`stream/start-client-133b.sh`, and client `--packet 133b`. Wire schemas and node
classes retain their inherited identities. Parent is 133, and its exact
manifest is a recursive dependency; changed parent bytes are preserved under
`provenance/packet133/`. The client pins the inner `plan_sha256`, not the hash
of its JSON envelope.

The new [sealed import gate](../recovery/20261010-continuation133b-stream/sealed_import_cpu.py)
runs in a fresh `bin/python -B` process at nice 19 with OMP_NUM_THREADS=2.
Its cwd is the launcher's repository cwd; its import path starts with the
sealed packet's `launch/`, followed only by interpreter library paths.
It imports the actual sealed `serve-encoder.py`, its common module and the
lazy environment-check dependencies, then checks the cached helper's oracle.
Author modules and author-tree fallback are excluded. Device opens, sockets,
subprocesses, writes, signals, locks and health-receipt work are blocked.
It never calls `launch`, `prepare_start` or `--check-only`.

The builder requires both split36 and legacy import checks before writing the
manifest. Six regression cases cover both modes, oracle coverage, the original
sealed133 failure, and injected missing helper/oracle failures. Fault injection
changes only the child import/read behavior, never packet files.

Full test counts, seal identities, recursive verification and cleanup are in
[the build receipt](../data/resume-20261008/continuation133b-build.json).
The exact future launch command is in
[LAUNCH.md](../recovery/20261010-continuation133b-stream/LAUNCH.md), with the
unchanged numerical and safety requirements in
[CONTRACT.md](../recovery/20261010-continuation133b-stream/CONTRACT.md).
Native qualification, memory and speed remain unmeasured by this rebuild.


## Reproduction and identities

Packet: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-133b`.
Manifest: `ed908a9031a937801d17264edacfe0807bea543badc412a32eb6118daa214fd3`.
Inner plan: `b67b1a8fe9b3457666190267a3ff020cd3708371d89de60952d1e0f60dafab7b`.
Input inventory: `099f203195a0b1681188fd1a0d6d3e2b80f5621068ee037a3537c6059f10b776`.

The builder's `--inspect-assembly` and `--build` operations were called with
that input inventory; `build()` runs recursive verification after its two
pre-seal import checks. A separate recursive verification passed for 2,313
bound files (2,315 physical files, including manifest and status). All ten
changed parent-bound files retain their exact originals in provenance; no
parent-bound file was deleted. All 220 numerical contracts and qualification
ids compare equal. The full recovery suite also checks 3,960 qualification
graphs and setup graphs after namespace/clip normalization.

All commands use this prefix, from the repository root:

```bash
nice -n 19 env OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 /home/steve/.venvs/ltx25-baseline/bin/python -B
```

Append the relevant script and arguments:

```text
experiments/ltx25-b70/recovery/20261010-continuation133b-stream/runtime_packet.py --inspect-assembly
experiments/ltx25-b70/recovery/20261010-continuation133b-stream/runtime_packet.py --build --input-inventory-sha256 099f203195a0b1681188fd1a0d6d3e2b80f5621068ee037a3537c6059f10b776
experiments/ltx25-b70/recovery/20261010-continuation133b-stream/run_tests_133b.py
experiments/ltx25-b70/recovery/20261010-continuation133b-stream/run_tests_133b.py test_sealed_import133b.py
experiments/ltx25-b70/recovery/20261010-continuation133b-stream/run_client_suites_133b.py
experiments/ltx25-b70/data/resume-20261008/continuation133b-runtime-validation.py --label fixtures-final --promote-final
experiments/ltx25-b70/data/resume-20261008/continuation133b-verify-packet.py
```

The build refuses an existing destination; test logs also use exclusive names.
For a new client-suite run, set TMPDIR to a newly created owned scratch root.
The recorded run used `continuation133b-tests/scratch` inside this lane's data
folder. No existing run tree or `/home/steve/ltx-stream` was used as scratch.
The two owned `/tmp/packet133b-*` planning outputs were deleted. The original
coordinator log under `/tmp/claude-1000` was read and copied, never removed.


## Development checks retained

An initial 16-case assembly/identity run had one stale run-prefix assertion
while re-identification was in progress; it was corrected before sealing.
A preassembly invocation of the six import regressions passed the original133
negative control and failed the five cases requiring the not-yet-created133b
path; it created no packet or scratch. The post-seal six-case run passed fully.

The first full recovery run completed 1,054/1,058 in 1,115.163 seconds. Its four
failures were inherited assertions for numeric packet133, parent132's name or
parent132's manifest hash. Those expectations were updated to string133b and
parent133. The log is retained as `recovery-development.log`; runtime sources
and sealed bytes were not changed by these fixture corrections. The complete
suite was rerun. Three CPU runtime cases were repeated after the fixture edits
so the final runtime summary binds the final author-source hashes. Earlier
runtime summaries and logs are retained as development evidence.


## Final CPU result

- Complete recovery discovery: **1,058/1,058**, no skips, 1,118.087 seconds.
- Sealed-import regressions: **6/6**, included in that recovery count; a separate
  focused run also passed. The two positive modes also passed before sealing.
- Full client regression: **6,351/6,351 across 43 suites**; new133b contract111/111
  and integration208/208, with all32 inner-plan assertions across16 packets.
- Mocked preflight: **10/10**. Three CPU runtime cases: **22/22** matching output
  comparisons (nine qualification plus two streaming outputs per case).
- Recursive verification: **2,313 bound files**, all author components match.
  Both helper and oracle are byte-identical to sealed133.
- Zero `__pycache__` directories and `.pyc` files in author and sealed133b trees.
  Owned scratch and the two owned `/tmp` planning files are removed.

These are CPU packaging/correctness tests. No model launch, launcher check-only,
GPU, port8188, unit, device-open, process-signal, host-setting, existing-run or
`/home/steve/ltx-stream` operation was performed.
