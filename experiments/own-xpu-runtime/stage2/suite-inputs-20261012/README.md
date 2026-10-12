# Arithmetic-v2 twelve-prompt CPU suite

Verified prompts: 1/12. Complete: False.
The unchanged sealed CPU binary generates greedy tokens for the fixed rendered suite.
Identity: `iq3-p17-detmath-v2`; 192-token context; maximum 64 generated tokens.
EOS (248044) or 248046 is saved and then stops generation. No padding or forced continuation.
The runtime uses the same stop rule. llama.cpp's immediate code-review EOG is information only.
Two OpenMP threads, nice 19, idle I/O; inherited CPU affinity, no device execution.

| Prompt | Prompt tokens | Generated | First 8 token IDs | Early end | Seconds/position |
| --- | ---: | ---: | --- | --- | ---: |
| incident-retrospective | 87 | 64 | 332, 37947, 1653, 10082, 3508, 8812, 25, 23288 | False | 20.4372 |

Total numerical-process wall time: 3068.110 seconds.
Actual process CPU time (user + system): 1.446575 CPU hours.
CPU accounting complete: True.
Position timings include bounded weight reads and CPU work; these are oracle costs, not serving speeds.
Every prompt retains `positions.jsonl`; means above include prefill and decode positions.

Incident equality: 64/64 token IDs, 64 logit hashes/top-five records, 384/384 raw BF16 fixtures and 8/8 layer hash ledgers exactly equal; see incident-retrospective/equality-proof.json in the oracle directory.
Timing and process metadata naturally differ. Input bundles are made by packet29 `prepare.py`;
`validation.json` proves `tokens.txt`, `input.json`, the oracle copy and consumed positions agree.

Retain raw 20,480-byte layer files for steps 1–8 (or through early EOS), tokens/text,
receipts and all timing evidence. Progress/timing site logs use deterministic gzip (mtime=0),
verified against original SHA256 before deleting raw copies. Keep teardown JSON uncompressed,
as in the sealed run. Files above 1 MiB are these same retained logs/teardown and each bundle's
2.84 MB `vocab.bin`, required by the runtime to decode tokens. No models or executables are committed.
Each compressed log's original hash/size is in its receipt. Restore with gzip and verify that hash.

Run from the repository root (Python environment needs the existing `regex` dependency):

```sh
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/steve/.venvs/vllm-xpu/bin/python -B experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-suite/suite_run.py --all --publish
nice -n 19 ionice -c 3 python3 -B experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-suite/suite_check.py RUNTIME_OUTPUTS
```

The checker accepts `RUNTIME_OUTPUTS/<prompt>/` or `<prompt>/run/`, reads runtime
`receipt.json` tokens, and compares raw step fixtures without tolerance. Using the oracle
suite directory itself tests the retained oracle files. It prints all twelve rows and fails
if any prompt is missing or incomplete. Unit tests include altered tokens, missing bytes,
corruption with a rewritten ledger, manifest tampering, early EOS and runtime nesting.
`checker-tests.json` pins the test/checker source and records the test result.

For packet29 `window.py`, pass `--input` the bundle directory and `--oracle` the matching
oracle directory from `suite-manifest.json`. The native program's `--input` takes that
bundle's `tokens.txt` instead. The frozen window gate assumes the requested token count;
an early-EOS oracle must not be padded to satisfy that assumption.

`status.json` is updated after each completed position. Each prompt runs in a private
`.partial-*` directory; after validation it is renamed to its final prompt ID. A restart
verifies completed prompt hashes and skips their computation; completed native partials
are recovered without rerunning. An interrupted unfinished prompt starts a new attempt,
retaining old partial evidence. A surviving oracle blocks duplicate launches. No automatic
retry occurs after native failure or packet31 disagreement. Completed prompts are committed
with explicit paths and pushed only when main is a fast-forward; no stash or branches.
The incident repeat's original launcher is retained under `runner-snapshots/` by hash;
subsequent launcher revisions preserve the same numerical binary and arithmetic.

This is oracle coverage, not a runtime speed result or the 512-token final performance gate.
Only incident-retrospective is a new full fresh-process repeat; other prompts have one new oracle run.
The reference screen uses two repeats; runtime qualification still requires its own repeats.
