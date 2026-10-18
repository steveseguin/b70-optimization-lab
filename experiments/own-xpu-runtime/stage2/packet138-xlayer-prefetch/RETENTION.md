# Retention and restoration

Keep source, provenance, metadata, checks and proposals in Git. `build/` is ignored
and reproducible with the README commands against hash-bound frozen parent objects.
Current build is about 67 MB. Do not remove any parent dependency or original packet.

The raw `evidence/capture-B/` tree is ignored and bounded at 1 GB. Keep it
until a verified byte-preserving archive and updated consumers exist. Its hashes
are in the tracked `evidence/capture-inputs.json`; that manifest does not replace
the binary bytes. The coordinator completed the capture on October 18. A copied oracle
folder is not acceptable: preserve the original authority symlink/binding.

The [disk7 cleanup record](../DISK-CLEANUP-20261018.md#disk7--verified-archive-pass-2026-10-18)
tracks the verified archive of selected closed capture/build files at
`/mnt/raid-models/own-xpu-runtime-archive/disk7-20261018/packet138-xlayer-prefetch-closed-bulk.tar.gz`.
Before rerunning `router_replay.py` or a historical build, verify the adjacent
archive SHA-256, extract `payload/` into scratch space, and verify every extracted
file against `.disk7/manifest.json`. Restore only its enumerated paths under the
manifest's original root, preserving existing files and links. The pinned
`evidence/capture-B/run/incident-retrospective/rank0/capture.bin` stays on root;
all capture JSON, compressed analysis JSON, notes and sources stay too. The
archive receipt and cleanup record distinguish completed moves from plans.

Retain `evidence/predictions.json.gz` (3,960,231 bytes, above the 1 MiB review
threshold) in Git. It contains the real route truth and all top-16 predictions
for every registered predictor, prompt, token and eligible layer. `simulate.py`
consumes these exact IDs; recall totals cannot reconstruct cache pollution or
copy timing. Restore it from Git, or reproduce it with `router_replay.py` using
the hash-bound raw captures, pinned GGUF router weights, CPU build and analysis
seal. Its result identity links the capture and exact replay. It is evidence,
not a generated compiler cache. Keep the smaller pinned prefill route stream too.
