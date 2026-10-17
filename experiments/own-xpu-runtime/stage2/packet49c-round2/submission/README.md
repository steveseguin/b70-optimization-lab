# Packet49c submission preparation

CPU-only tooling, staged before WS128 exists. No new result or submission is
claimed. The current two-card record is 39.422009 class-balanced tok/s, packet45
SPEED6 `34c62b433`, LocalMaxxing `cmv9wjmtj013gle01v8k1yg4v`.

After the registered `device-cards01-a` chain finishes WS128, run from the repo:

```bash
bash experiments/own-xpu-runtime/stage2/packet49c-round2/submission/prepare_submission.sh
```

This runs every Python command with `nice -n 19`, `taskset -c 4-15,20-31` and
`python3 -B`. It builds `submission/prepared/`, runs the helper's local dry-run,
then its authenticated server dry-run, and stops. It has no real-submit command,
retry, GPU command, service operation or credential output. The helper reads its
usual API-key file directly. Neither dry-run was run during pre-staging.

The builder is [`scripts/packet49_submission.py`](../../../../../scripts/packet49_submission.py).
Its defaults read only:

- `/home/steve/own-xpu-runtime-results/packet49c-round2/build/device-cards01-a/`;
- `/home/steve/own-xpu-runtime-results/packet49-integrate/oracle/results/`;
- the immutable packet seal, oracle sources and frozen suite metadata in Git.

It never imports or runs the runtime, oracle job, device probes or sealed scripts.
It writes only a new directory beneath a lineage's `submission/`. Existing output
is refused; failed evidence checks happen before output creation. A failure during
writing may leave partial evidence but no eligible queue: the queue is written last.
Keep partial outputs for diagnosis. To make a new output after fixing a preparation
problem, pass its new path as the wrapper's only argument. Do not substitute a
repeat chain, a higher score or a different card pair.

For offline preparation only, omit both helper commands and run:

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B scripts/packet49_submission.py
```

The same evidence parser supports `--packet packet49-integrate`,
`packet49b-gemv` and `packet49c-round2`. Only the pinned 49c identity emits a payload
queue or receives the helper's owner-scope exception. Earlier lineage packets can
produce evidence and document drafts, not newly authorized submissions.

## Identity and refusal checks

49c seal: `2ebe64adc810d7560c23f2674117c424caf360a4e7c3b75217eb25aa0b900dd7`.
Sealed build base (`parent_commit`): `192ee28f2`. This is a build-base field;
the seal's source inventory identifies the actual code overlay. The submission
helper pins both fields. Its SPEED3/SPEED6 registry and literal headlines stay
unchanged. No literal candidate headline or generated numeric allow-list is needed:
`tokSOut` must equal the result recomputed from the portable, hash-bound receipts.

Preparation and helper validation refuse:

- Missing, changed, failed, diagnostic-unsealed, CPU-only or mismatched window
  receipts; wrong seal, model/suite identity, arithmetic, card pair, split, draft,
  context, dispatch or boot; reused rank PIDs or unfinished teardown.
- New fault signatures in any retained window tail or later preflight journal. Historical preflight faults
  are kept verbatim and do not imply a newly clean boot.
- Incomplete or changed CPU oracle completion, sources, determinism or prompt
  outputs; prompt inputs that differ from the frozen realistic suite.
- Any non-exact emitted token, missing prompt, repeated prompt, cached token,
  incorrect cap, missing checker evidence or missing WS128x companion binding.
- Missing KD owner/fixture comparisons, incomplete quality windows, or a speed
  request that retained fixtures or used diagnostic timing.
- Nonfinite, non-increasing or out-of-bounds timestamps; inconsistent timing
  accounting; a class-balanced median **at or below 39.422009 tok/s**.
- Altered result, bundle, attestation or payload hashes; a hand-edited headline,
  authorization, scope or strict-gate marker; overwriting a previous preparation.

Arithmetic is explicitly `iq3-p49-split32-v1`: exact to the packet49 line's own CPU
reference. It is not claimed bit-identical to SPEED6's earlier arithmetic. The
**strict 512-cap gate stays false**, including the unedited raw gate reason.
Standard 512-input-token prefill and 512-token natural completion remain unmeasured.
Independent exactness windows qualify repeat determinism; they are not pooled as
additional speed runs. One preregistered WS128 supplies the headline.

## Output and retention

`prepared/` contains `result.json`, `promotion-attestation.json`, `evidence.json.gz`,
`payload-queue.json`, `result-packet.md` and `ledger-entry.md`. The Markdown files
come from the two `.md.in` templates here; all candidate rates come from computation.
The ledger draft explicitly says **not submitted** and never edits the actual ledger.

The bundle is a gzip JSON object. Text/receipt `members` contain `source_path`, `sha256` and `raw_base64`
preserving the original bytes. Decode and hash a member to restore it. KD binary
fixture members instead have `retention: sha256-only`, `bytes` and `sha256`; their
original files remain in the external chain. Windows, raw request receipts, oracle results, dispatch and journal
files are retained; no weights or runtime binaries are copied. KD fixture bytes are streamed through SHA256 once and retained as digest/size
records alongside the original native comparison receipts. The two large, repeated
KD binary payloads are not copied into the bundle. The existing KD host-reference
archive is retained. Other layer-fixture exactness comes from the original hashed checker
receipts, matching SPEED6's evidence boundary. No model or device work is rerun.

The generated bundle may exceed 1 MiB. Retain it with the result and attestation:
it is required to replay validation from a checkout without the external chain.
It is not a cache and must not be removed for size alone. Original host artifacts
are untouched; regeneration requires their exact original bytes. The coordinator
must commit the generated evidence and retain the server dry-run response before
real submission. Then fill the ledger template with the actual response ID/date;
do not record the draft as an accepted public record.

## Tests

```bash
PYTHONPATH=scripts nice -n 19 taskset -c 4-15,20-31 python3 -B -m pytest scripts/tests -q
```

On this host the system Python lacks pytest. Validation used the already installed
`/home/steve/.venvs/deepseek-v4-xpu/bin/python3` with `-B`,
`PYTHONPATH=scripts`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `-p no:cacheprovider`, and the
same priority/affinity. No environment was installed or changed. The pre-stage run
passed **159 tests and 31 subtests**, including 41 synthetic submission-path cases.
The shell wrapper passed `bash -n`; stub-launcher tests verify both dry-run flags,
stop-on-failure and absence of any real submission command.
