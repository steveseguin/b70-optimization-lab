# Native references generated; verifier convention corrected — October 7, 2026

Packet101b (`5105769afe404cfa7343d03f3fb3b95a6b50fdff26b2accd670705622d574c59`)
passed its encoder check and full native residency preparation. The live inventory
confirmed exactly four constructor-owned FP32 tensors totaling41,540bytes;
original BF16 checkpoint weights and placement checks remained intact. Initial
physical free GPU memory was8.73/12.80/11.84/14.85GiB.

All six planned native requests completed, with finite raw F32 captures. Each
of the three fixed scenes repeated identically across video, audio, images and
waveform. Warm native request wall time was about6.7seconds; this is preparation
and reference evidence, not an optimized throughput result.

The final verifier refused before optimized setup because it compared raw-text
SHA256 to the pipeline-window job tag. The pinned producer intentionally hashes
`pipeline-window\n` followed by the text to separate window and full-text jobs.
Both `detail.tag` and the historical `detail.text_sha256` field contain that tag.
The new verifier and its synthetic fixtures assumed the wrong convention.
A producer-rooted CPU regression now executes the exact two hash-pinned tag
functions and rejects substitution of a raw-text digest. The candidate verifier
contained the same assumption and is being corrected too.

A separate CPU-only diagnostic audited all actual101b reference artifacts with
the corrected convention. It checked73 bound evidence files, all execution and
source identities, all remaining verifier fields, all finite tensor payloads,
repeat pairs and conditioning fingerprints. It passed those checks. The diagnostic
skipped only the two known session-halt checks in memory, wrote no accepted
receipt, and left the original halt and failure artifacts unchanged. It is
**not a runtime qualification receipt** and cannot authorize an optimized request.

The application stopped gracefully at16:24UTC with one SIGINT and no retry.
[Postflight](../data/resume-20261007/postflight-101b.json) passed on all four GPUs,
with no fault lines on this boot. The [closeout](../data/resume-20261007/resolution101b-closeout/summary.json)
binds143 files, including all six raw outputs retained outside Git. An independent
[repeat-hash diagnostic](../data/resume-20261007/resolution101b-closeout/native-repeat-hash-diagnostic.json)
is included; no native or failed evidence is retired.

Next: packet101c uses new names and indices for all32 requests, preserving the
same fixtures, seeds, shapes, precision and8+3 arithmetic. It must pass the
corrected prospective verifier before optimized capture/timing. Review remaining
candidate fields against actual historical producers before that launch.
