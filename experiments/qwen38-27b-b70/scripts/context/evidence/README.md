# Validated context trial exports

This CPU-only tool imports completed and unfinished Harbor attempts without
running inference or changing the experiment harness. It produces one canonical
numeric manifest, a Markdown table, and a machine-readable site projection.
It never multiplies a rounded reward by an assumed question count.

```bash
python3 export_trials.py --review-index /path/to/review/evidence.json --output /tmp/context-export
python3 export_trials.py --root /path/to/Harbor/campaign --output /tmp/context-export
python3 -m unittest discover -s . -p 'test_*.py'
```

Both input switches can be repeated or combined. `--root` accepts a trial, job,
or campaign directory. The review importer validates the frozen review's copied
grader, task metadata, expected answers and summary against their recorded hashes.
It does not require the originating host's raw files. Source files without copies
remain explicitly recorded hashes, not claims that their bytes were rechecked.

Malformed counts, missing required task evidence, inconsistent expected-answer
counts, invalid hashes, contradictory scores and empty input selections fail the
export before any output is written. Each attempt stays separate, including void
results and interruptions. An unfinished record has no inferred score. A missing
peak-context measurement stays null. A job summary is never attributed to one
attempt when the job contains multiple attempts.

`manifest.json` uses `context-trial-manifest.v1`. Each row contains a stable trial
directory ID, original record ID, arm, task family, seed, token count, density,
mode, exact correct/asked counts, boolean void flag, lifecycle status, numeric
timings/token counts, version provenance and source hashes. `completed` means
the trial ended with verifier evidence; a completed trial can still be void or
wrong. `interrupted` means the raw result records an exception. `incomplete`
means no finished result or no verifier evidence. Invalid evidence is an export
error, never a successful row.

Task fingerprints bind the stream and expected-answer hashes. The fingerprint
is SHA256 of UTF-8 JSON with sorted keys, indentation two, unescaped Unicode and
a trailing newline, for `{"stream": stream_sha256, "expected": expected_sha256}`.
The fingerprint is null if either source hash is unavailable. It identifies
task content, not the harness, checker, model or runtime. These versions remain
explicitly unknown unless recorded by a source; the current Git checkout is not
retroactively assigned to an old trial.

`sources/` contains exact compact source copies addressed by the manifest.
Raw configs and trial results are hashed but not copied because they may contain
connection credentials. Model names and selected budget/archive settings are
retained, not arbitrary configuration environments or kwargs. The importer does
not create a complete runtime-reproduction package.

`site_projection.json` contains the same numeric rows plus the manifest SHA256.
`results.md` is rendered from those rows too. Site selection should be explicit
by trial ID; select neither the best score nor the last directory implicitly.
Deterministic output has no export timestamp. Identical inputs yield identical
bytes; changed live input is a new snapshot, not a reproducibility failure.
