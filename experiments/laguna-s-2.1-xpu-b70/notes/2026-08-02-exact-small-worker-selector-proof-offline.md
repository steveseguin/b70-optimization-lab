# Laguna exact-small worker selector proof: offline implementation

Date: 2026-08-02 America/Toronto

Status: **OFFLINE-VALIDATED ONLY — no model run, device probe, score, or run
authorization.** The consumed swap24 smoke proved that post-`setproctitle`
`/proc/<worker>/environ` is not a reliable absence-proof source. This work
replaces that assumption in code without modifying the consumed runner or lock.

## Worker emitter

The isolated vLLM worktree is
`/home/steve/src/laguna-vllm-worker-selector-evidence-20260803`, branch
`experiment/laguna-worker-selector-evidence-20260803`, commit
`d6a509e6f5bddd4c426ff970da4243c3af3e5306`, based on frozen exact-small
commit `0c9dea8cf9aa46c1854d5bce8f4dfb180732b16d`.

When `LAGUNA_EXACT_SMALL_WORKER_SELECTOR_EVIDENCE=1`, each `WorkerProc` now
validates the exact 21 string-valued selectors formerly grepped from proc.
The lexicographically sorted `NAME=value` contract has SHA-256
`fef0594c56fb917c212af09b5b7573acf528bbcc4ebd46543179994282ba8f52`.
Missing or mismatched selectors abort before model loading and report key names
only, never observed values. A passing worker emits one compact canonical JSON
record containing the normalized frozen map, contract hash/count, PID and Linux
start ticks, final worker name, world size, and global/local/TP/EP ranks. The
hook order is:

```text
init_device -> final TP/EP process title -> validate/emit -> load_model
```

The opt-in-disabled path emits nothing. The helper uses only the standard
library and never enumerates the ambient environment, so unrelated credentials
cannot enter the record.

Source hashes:

- `vllm/v1/executor/laguna_selector_evidence.py`:
  `f928404212a6886ac4408b6a478617ca5a586b43ddd3e60b7c19256aac32d049`;
- `vllm/v1/executor/multiproc_executor.py`:
  `e7a0a503a82bc5252cedba686bc080ed193d9bc1b5ed086855415b372111c54b`;
- `tests/v1/executor/test_laguna_selector_evidence.py`:
  `21247be7bf786fa12e8b70429298c5cfdb69d154fa2f1618c3c2aa902f6bdef4`.

The isolated host-only suite passes 21/21 with pytest plugin autoload and vLLM
conftest disabled. It loads only the standard-library helper by file path and
uses AST for the executor wiring contract; it does not import vLLM, Torch, or
an XPU runtime.

## Host validator

`tools/validate_laguna_worker_selector_evidence.py` independently hard-codes
the same exact selector map and contract hash. It fails closed unless the fresh
server log contains exactly four canonical records with:

- ranks `{0,1,2,3}` and `global == local == tp == ep`;
- four distinct positive PIDs and start ticks;
- names `Worker_TP0_EP0` through `Worker_TP3_EP3`;
- the exact schema, field sets, count, hash, and 21 string values.

It rejects duplicate JSON keys, non-finite or noncanonical JSON, extra/missing
fields, type drift, identity drift, and any selector drift. It then uses the
emitted PIDs—not `pgrep`—for the independent grouped-GEMM proof. Linux process
start ticks are checked before and after reading each maps file. The validator
opens the expected DSO once, hashes that descriptor before and after all maps
checks, and binds its `fstat` device/inode to each worker mapping. The single
mapped `libgrouped_gemm_xe_2.so` must also resolve to the lock-bound path,
and that pathname must still name the descriptor-bound inode before success,
closing pathname-replacement, hash-substitution, and PID-reuse gaps.

Only after both selector and maps validation succeed are the two canonical
mode-0600 outputs published. Creation is exclusive/no-follow; partial files are
removed by proven inode, and failure of the second publication removes the
first rather than leaving an unpaired success artifact. The standalone
validator suite passes 17/17, including every frozen selector's missing/wrong
case, duplicate/noncanonical records, PID/rank drift, pathname inode and
hash-window replacement, initial metadata/chmod failures, and
partial/paired-publication failure.

Host-tool hashes:

- `tools/validate_laguna_worker_selector_evidence.py`:
  `b7bb4e5ee439262b2db0e01a26ae7da29f71fb011320a2907f154d534457b500`;
- `tools/test_laguna_worker_selector_evidence.py`:
  `127d2505d4464b8eb62d45888c35c1b11c127335adaf666efb66e5324a99a91b`.

## Integration boundary

The consumed runner, lock, and tag remain unchanged. They still contain the
historical proc-environment proof and must not be retried or silently edited.
Before any future model attempt, a separately named successor must be
preregistered and lock all of the following:

1. vLLM commit `d6a509e6f5bddd4c426ff970da4243c3af3e5306`;
2. the evidence arm and INFO-level worker logging;
3. this validator and its exact 21-value contract/hash;
4. the literal grouped-GEMM path and SHA-256 from that successor's runtime lock;
5. validator execution after health but before any request, with both paired
   outputs and exit status required;
6. removal of worker `/proc/environ` and `pgrep` as selector/PID proof sources.

The corrected root-filesystem NVMe PCIe events from the consumed smoke still
prohibit a new heavy run, XPU probe, reset, reload, reboot, or recovery action
without separate authorization. This note records offline readiness only.
