# Retention and restoration

Keep source, provenance, metadata, checks and proposals in Git. `build/` is ignored
and reproducible with the README commands against hash-bound frozen parent objects.
Current build is about 67 MB. Do not remove any parent dependency or original packet.

The raw `evidence/capture-B/` tree is ignored and bounded at 1 GB. Keep it
until a verified byte-preserving archive and updated consumers exist. Its hashes
are in the tracked `evidence/capture-inputs.json`; that manifest does not replace
the binary bytes. The coordinator completed the capture on October 18. A copied oracle
folder is not acceptable: preserve the original authority symlink/binding.

Retain `evidence/predictions.json.gz` (3,960,231 bytes, above the 1 MiB review
threshold) in Git. It contains the real route truth and all top-16 predictions
for every registered predictor, prompt, token and eligible layer. `simulate.py`
consumes these exact IDs; recall totals cannot reconstruct cache pollution or
copy timing. Restore it from Git, or reproduce it with `router_replay.py` using
the hash-bound raw captures, pinned GGUF router weights, CPU build and analysis
seal. Its result identity links the capture and exact replay. It is evidence,
not a generated compiler cache. Keep the smaller pinned prefill route stream too.
