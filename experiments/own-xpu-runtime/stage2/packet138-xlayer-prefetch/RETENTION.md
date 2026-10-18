# Retention and restoration

Keep source, provenance, metadata, checks and proposals in Git. `build/` is ignored
and reproducible with the README commands against hash-bound frozen parent objects.
Current build is about 67 MB. Do not remove any parent dependency or original packet.

The future raw `evidence/capture-B/` tree is ignored and bounded at 1 GB. Keep it
until a verified byte-preserving archive and updated consumers exist. Its hashes
will be in the tracked `evidence/capture-inputs.json`; that manifest does not replace
the binary bytes. No raw capture exists at CPU preparation time. A copied oracle
folder is not acceptable: preserve the original authority symlink/binding.
