# CPU long-context oracle campaign

Owner scope: two exact arithmetic-v2 CPU references for packet44's context extension.
All writes are confined to this directory and stage2/long-inputs-20261012, apart from
authorized Git main commits/fetch/merge/push. No GPU executable, device discovery,
/dev/dri access, sudo, host setting change, branches, stash or unrelated file edits.

Fixed identity: the sealed iq3-p17-detmath-v2 sources and compiler options. The local
host adapter has a two-constant temporary scratch allocation/bound extension from
256 to 512 MiB; scratch-analysis.json gives the exact capacity proof and Core-only
probe. There are no numerical operation changes. Build artifacts are ignored.

Stages, in order:

1. At context4096, the complete sealed 87-input/64-output incident replay: exact
   tokens, top-five logits, logit hashes, step1–8 layer bytes and ledgers.
2. A six-input/eight-output checkpoint diagnostic: one uninterrupted run and a
   run stopped at positions-completed4 and8, resumed in fresh processes. Exact
   tokens/logits/384 layer fixtures/ledgers and mid-prompt observations must match.
   This synthetic diagnostic is not one of the two long references.
3. LONG-A: 598 rendered tokens from one corpus prose source; cap32/context4096.
   Seal only after complete validation and checker corruption tests; commit/push.
4. LONG-B: 2271 rendered tokens from a different corpus prose source; cap32/context4096.
   Retain requested zero-based indices2040,2048,2049,2100,2270, plus2047,2050,2051.
   Seal only after complete validation and checker corruption tests; commit/push.

Checkpoint every100 completed positions; atomic write/readback/rename. All plan
buffers and generation/log metadata are saved. Explicit --resume is permitted for
cooperative interruption/deadline, never for a numerical failure. No automatic
retry of a failed process. Each native launch is bounded to72hours. Each process
gets2 OpenMP threads, inherited4–15,20–31 affinity, nice19 and idle I/O. The runner
admits at most2 oracle processes and leaves room under the8-thread limit for helpers.
Combined oracle anonymous-memory stop is11.5GB. Model files are read-only.

Disk floor8,000,000,000bytes on root, checked with df -B1 / before builds, checkpoint
writes, compression and teardown and every10seconds during a run. Scratch<2GB.
Site logs rotate every100positions and compress losslessly with restored hashes.
All failed/partial evidence is retained and labeled. Only regenerable checkpoint
scratch is removed after a completely validated run. Status writes after each position.

EOG248044/248046 is retained and stops generation. Never force continuation.
Generation layer fixtures retain the suite's exact layout. Selection records preserve
ordered full2051-slot int32 buffers, trailing-1 padding, per-layer admitted lists,
pool-score FP32 bits/ties, and layer47 BF16 stream. All position fields are zero-based;
prompt_ordinal states one-based consumed length.

Measured CPU position times will be grouped by context range and actual process
wall/CPU totals reported. Checkpoint/resume overhead is separately identifiable.
QSA and frozen allocation-history scanning both contribute to growth; neither CPU
cost nor successful arithmetic gates establish a GPU serving speed or quality result.

Preparation history: two incomplete short replays were stopped cooperatively while
review found the scratch bound and final teardown storage check. They are retained
under preparation-stopped-* and are not counted as capacity passes or long oracles.
