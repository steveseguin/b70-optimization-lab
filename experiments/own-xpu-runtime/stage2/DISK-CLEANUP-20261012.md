# Disk-full incident and cleanup, 2026-10-12 about 04:57–05:05 UTC

The root filesystem (915 GB, 13 GB free at the start of the night) reached 100% while
five packets were building and their windows were running: each packet's ignored
`build/` tree holds 2.5–7 GB (three host compilers, a sanitizer build, CPU fixture
outputs, and raw fixture outputs of the K1/K2 windows at 355–977 MB each).

What broke: packet 36's K2 window on card 0 ended with an empty receipt
(`JSONDecodeError` in the wrapper; no GPU fault line), which stopped the rest of its
chain; the Codex job building packet 38 exited (rc 101); command output of the
coordinator's shell was lost for a few minutes.

What was removed (all ignored, regenerable build output; nothing tracked, no receipt):

1. `packet17-detmath/build/wa-gnu-reference-diagnostic/wa-reference/` (14 GB): the
   diagnostic GNU duplicate of the exhaustive reference tables. Its hash manifest is
   tracked (`packet17-detmath/evidence/wa-gnu-reference-diagnostic.json`); generator
   identity and log stay in place. The sealed `build/wa-reference/` (14 GB) is kept.
2. In packets 23, 24, 26, 27, 29 and 35 (finished or abandoned lines): sanitizer builds,
   CPU fixture scratch directories and every raw fixture `output.bin` above 20 MB
   (their SHA-256 is in the adjacent `receipt.json` and, for the runs that matter, in
   the tracked receipts folders); raw `events.jsonl` above 20 MB were compressed in
   place. 13.1 GB. The exact list is [DISK-CLEANUP-20261012.txt](DISK-CLEANUP-20261012.txt).

Free space afterwards: 27 GB. Rule for later packets: keep a build tree under 3 GB,
delete CPU fixture scratch as soon as its gate receipt is written, and stop before a
large write if less than 8 GB is free.
