# Laguna exact-small worker-proof successor component

Date: 2026-08-02 America/Toronto

Status: **OFFLINE-VALIDATED COMPONENT ONLY — no tag, run root, caller,
execution lock, model run, device probe, or retry is authorized.** The corrected
root-filesystem NVMe PCIe events from the consumed swap24 smoke remain a hard
stop on further heavy or privileged activity without separate authorization.

## Purpose and lineage

The consumed exact-small measurement leg remains unchanged at SHA-256
`3791fb261c0bc31f3628de079931c465020143e81a832105ccc2aa8b1252797f`.
Its post-health exact-small block used `pgrep` plus each worker's
`/proc/<pid>/environ`; `setproctitle` made that worker environment source
unreliable, so the one authorized smoke stopped before any request.

`tools/run_laguna_worker_proof_measurement_leg.sh` is a separately named copy
whose semantic delta is the replacement proof path plus fail-closed freezing
of the exact-small identity that the consumed caller previously supplied. It
does not modify or reactivate the consumed runner, lock, tag, or roots.

## Frozen successor inputs

- vLLM worktree:
  `/home/steve/src/laguna-vllm-worker-selector-evidence-20260803`;
- vLLM commit: `d6a509e6f5bddd4c426ff970da4243c3af3e5306`, based on
  `0c9dea8cf9aa46c1854d5bce8f4dfb180732b16d`;
- kernel worktree:
  `/home/steve/src/laguna-xpu-kernels-exact-small-portfolio-20260801`, commit
  `46a6393fc188c11661ddab9cf1320d2f3de45087`;
- grouped-GEMM SHA-256:
  `5d2d29e63f40c62d31b61808d74a0ef7ba71f2c6a62754c3220ed4d0c8281d4b`;
- worker evidence helper SHA-256:
  `f928404212a6886ac4408b6a478617ca5a586b43ddd3e60b7c19256aac32d049`;
- multiprocess executor SHA-256:
  `e7a0a503a82bc5252cedba686bc080ed193d9bc1b5ed086855415b372111c54b`;
- host validator SHA-256:
  `744554c9599091966b8cba0af1ae744d816b5ba599689dbb2c80c3ff6563210f`;
- exact 21-value contract SHA-256:
  `fef0594c56fb917c212af09b5b7573acf528bbcc4ebd46543179994282ba8f52`.

The new runtime identity file is
`data/laguna-exact-small-worker-proof-runtime-lock-20260803.json`. Relative to
the prior exact-small portfolio runtime lock, only the descriptive scope and
vLLM provenance change. All host, package, native module, mapped library,
model, and runtime-file identities remain byte-for-byte identical. This is a
runtime identity input, not an execution lock. Its SHA-256 is
`90591f46c8b9204d6e967a825a57a8d2e7c58d0a055ab43a1caafe232314993f`.

The successor leg hard-codes those vLLM/kernel/runtime paths, their source
commits, the exact native hashes, teacher identity, collective interface, and
the grouped-GEMM path/hash. It accepts no `REPRO_*` override, so a caller
cannot substitute a self-consistent but wrong runtime lock, kernel tree, DSO,
or expected hash. It also rejects every inherited `PYTHON*` variable before
any Python helper can run.

## Fail-closed order

The successor leg:

1. requires the frozen exact-small selector combination before service work;
2. requires clean source trees, vLLM commit `d6a509e6`, kernel commit
   `46a6393`, the successor runtime identity, exact native/DSO hashes, and
   exact hashes for the helper, executor, and host validator;
3. starts the service under `env -i` with
   `LAGUNA_EXACT_SMALL_WORKER_SELECTOR_EVIDENCE=1` and
   `VLLM_LOGGING_LEVEL=INFO`;
4. waits for API health, which can occur only after all four workers validate
   and emit before model loading completes;
5. invokes the pinned host validator directly, with the server log, paired
   exclusive JSONL outputs, literal candidate grouped-GEMM path, and frozen
   grouped-GEMM SHA-256. The validator runs under a minimal `env -i` with
   isolated/no-site Python (`-I -S`) after the interpreter and validator are
   rehashed. The earlier idle helper also runs under a scrubbed no-site
   environment. The leg requires both regular, non-symlinked outputs to be
   nonempty with exactly four records;
6. permits metrics, inference, or any smoke/scored benchmark request code only
   after that validator exits zero. Health polls are the only earlier HTTP
   requests and are required to prove model initialization completed after all
   four pre-load worker emissions.

The replacement block does not use `pgrep` or worker `/proc/<pid>/environ`.
The validator gets all four PID/start-time identities from worker-emitted
records and uses live `/proc` only for start-time and mapped-DSO proof. The
leg does not expose a `--proc-root` override. The existing parent service
environment record and general cleanup/process checks remain unchanged and
are not used as worker selector evidence.

## Offline validation

The dedicated structural suite passes 10/10. It proves the consumed leg hash is
unchanged, Bash syntax is valid, the successor pins all proof and runtime
sources without caller overrides, the service launch contains every exact
selector plus the arm/INFO setting, the validator occurs after health and
before metrics or inference, paired outputs and literal DSO identity are
passed, Python startup injection is excluded and both outputs are checked, the
pre-proof interpreter/validator are rehashed, the legacy worker proof is absent
from the replacement block, and the successor runtime lock changes only the
stated provenance fields.

The underlying host validator remains 17/17 and the isolated vLLM emitter
suite remains 21/21. Ruff and whitespace checks pass. `shellcheck` is not
installed on this host, so only `bash -n` is claimed for shell syntax. No
runtime verifier was executed because it imports native XPU modules; the
runtime-lock equivalence check is JSON-only and does not load a device runtime.

Component hashes:

- successor runtime identity:
  `90591f46c8b9204d6e967a825a57a8d2e7c58d0a055ab43a1caafe232314993f`;
- successor measurement leg:
  `503e3cf3a5da6520f38c07dd8ead95dd36ce8fe9e8d0de4c939cea7845abe5c3`;
- structural test:
  `eba88cc42f16a0eb28a9b1c98b9b9133d7ff7838098520b0003f1089fd2352d9`.

## Remaining authorization boundary

This component cannot be run directly as an authorized experiment. A future
transaction still requires all of the following, in order:

1. separate authorization to proceed after the corrected NVMe events;
2. a separately named resource/core wrapper that invokes this leg under a
   clean environment and independently pins its frozen vLLM, kernel, runtime,
   and native identity;
3. a fresh tag and three fresh resource/campaign/smoke roots;
4. a committed preregistration defining the non-scored request and stop rules;
5. a reviewed harness commit followed by a non-self-referential lock-only
   commit that pins every file, source commit, native hash, validator hash,
   runtime identity, exact DSO path/hash, and fresh root;
6. explicit confirmation that the new one-shot execution lock—not either
   consumed lock—is the sole entry point.

No successor outer/core wrapper or execution lock is created in this
transaction, so no authorized successor entry point exists.
