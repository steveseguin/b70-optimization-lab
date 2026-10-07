# Process-local packet 98 integration candidate

The owner resumed LTX lossless optimization on October 7. The new
`launch_with_progress_lock.py` applies the existing, hash-bound `refresh()`
exception-safety candidate in one process, then delegates to the unchanged
sealed packet 98 launcher. It neither modifies the installed tqdm package nor
reseals packet 98. This is an additional runtime overlay and must be recorded
alongside the historical packet identity in every result. It is CPU-verified,
not yet a GPU result or output-parity qualification.

The sealed launcher ends with `runpy.run_path(source/main.py)` in its own
interpreter, so the changed tqdm class survives. A private copy of the whole
tqdm package and a `sitecustomize` import hook are unnecessary. The launcher
still runs its original admission, identity and fault checks. The wrapper
keeps the actual launcher path as a command-line token, so the campaign's
existing `/proc/PID/cmdline` and process-start-time checks continue to work.
The wrapper pins the exact installed source, original and candidate method,
launcher and packet manifest before delegation. It also rejects an already
modified loaded function. Its external, exclusive receipt is fsynced before
launch, binds its own hash and PID/start ticks, and explicitly makes no server
success claim. `LTX_PROGRESS_LOCK_RECEIPT` and its SHA256 environment value
carry that binding into the server. A result collector must copy and link this
receipt separately; the old sealed server-identity schema has not changed.

The wrapper changes `refresh()` only. It propagates display exceptions and
cannot fix a lock leaked in another process. Other tqdm paths and artifact
writes still need their own error handling. The normal rendered output and
`nolock`/`lock_args` behavior are covered by the original regression.

## CPU validation

Run these separately from an application launch:

```bash
timeout 15 /home/steve/.venvs/ltx25-baseline/bin/python -B \
  experiments/ltx25-b70/recovery/20261007-progress-lock/test_progress_lock.py
timeout 15 /home/steve/.venvs/ltx25-baseline/bin/python -B \
  experiments/ltx25-b70/recovery/20261007-progress-lock/test_launch_with_progress_lock.py
```

The original 10 regression controls pass. The wrapper's 8 controls include
loaded-function and source/candidate hash refusal, fixed manifest/launcher
checks, same-process fake-launcher propagation, receipt exclusivity/symlink
refusal, and refusal to delegate when receipt storage fails. They never execute
the real launcher or touch models or devices. Packet 98's separate 24 CPU
controls also passed using the documented disposable `sitecustomize.py` guard
and a 180-second subprocess bound; the log is preserved in
`../../data/resume-20261007/packet98-guarded-cpu.log`. The combined 18 progress
controls and real sealed launcher through the wrapper with `--check-only`
also pass. Commands, source hashes, log hashes and limits are preserved in
`../../data/resume-20261007/progress-overlay-cpu-review.json`.

## Launch shape for owner-controlled integration

This is an argument shape, not a complete host-admission recipe. Use the exact
existing packet's environment and a fresh health receipt, owned run name, log
and external overlay receipt. Only inactive `--check-only` delegation has been performed by this
audit; no application was started. Do not use a historical campaign as a restart loop.

```text
/home/steve/.venvs/ltx25-baseline/bin/python -B <this-directory>/launch_with_progress_lock.py
  --receipt <absolute-new-external-receipt.json>
  /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-size-98/launch/serve-encoder.py
  --packet /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-size-98
  --manifest-sha256 918b47a5530b4dc97fe8fc8f4ec77fd64521ec6846217c54f5fba589e0e8377f
  --run-name <owned-unused-packet98-run-name>
  --health-receipt <fresh-owner-verified-health-receipt>
```

First retain the 256×256, 25-frame, two-stage BF16 batch-1 control against w93c:
two sampler workers, shared pools and decode replica card 2. Packet 97's
1.308 s/clip, 126/126 exact result is the matching prior point. Batch 2/4
references are different outputs; larger sizes are speed-only, with no saved
output oracle. No new speed result should be promoted from these CPU checks.

## Storage and application risks still requiring admission

- Sealed `launch/serve-encoder.py:241` checks only 5 GiB free at startup;
  `run-campaign-98.sh:79` creates its output before later admission and has no
  ongoing free-space guard. Require the current 50 GiB root reserve plus the
  explicit run's worst-case artifact/log allowance before starting. The actual
  run, repository receipt and log filesystems all matter.
- Logs, request histories, tensor/artifact receipts and `engine-busy.jsonl`
  can continue growing. Select finite prompt counts and monitor free bytes
  and inodes independently; stop new requests before exhausting the admitted
  budget. Preserve research logs rather than truncate or silently rotate away
  evidence. Historical `sync` calls flush data but do not create capacity.
- `source/scripts/ltx_pipeline.py:163` catches errors writing failed-job
  evidence, then also catches stderr failures. Under ENOSPC both channels can
  disappear even though a worker failed. The wrapper's lock release avoids
  one deadlock path; it does not make disk-full operation reliable.
- In the sealed launcher's `fault()` (around line 318), a journal/FAULT write
  can itself fail before the processing interrupt. Independent storage
  monitoring must halt submissions while its receipt channel is still usable;
  do not rely on a full disk to report its own failure.
- The historical campaign finishes by proven-quiescence single SIGINT and
  refuses escalation. Reusing one application for successive measurements
  requires a deliberately scoped runner integration; the progress wrapper does
  not change lifecycle behavior or justify blind restart chains.
