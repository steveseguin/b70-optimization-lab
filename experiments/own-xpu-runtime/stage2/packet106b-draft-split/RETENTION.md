# Local evidence retention

`evidence/generated-cpu-evidence.tar.gz` contains generated source and the raw
CPU receipts, including one completed receipt per composition/window. It is
needed to audit the generated mock source against the production source and
resume interrupted gates. The archive is byte-verified member by member by
`retain_build.py`; `evidence/build-retention.json` records every original hash
and size. No original evidence is deleted or consolidated away.

Run `restore_links.py` with the documented CPU limits to restore missing
generated source and receipt files; it rejects path escapes and changed files.
Device/host binaries and object caches are excluded from Git. Rebuild through
`build_engine.py` using the pinned frozen parent objects and compiler commands.
The inherited object and CPU fixture links are immutable local dependencies,
not newly produced build bytes. Their actual byte hashes remain in receipts.
This is a local lab reproduction, not a public portable recipe.

The combined new build limit is 250,000,000 bytes, excluding links to frozen
inputs. No weights, services, or model requests run during CPU preparation.
