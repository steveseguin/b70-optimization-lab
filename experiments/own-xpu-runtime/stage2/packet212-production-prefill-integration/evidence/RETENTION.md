# Native symbol inventory retention

`build-1792802843616050951/native-symbols.log` is the complete 5,265,864-byte
offline symbol inventory of the compiled candidate. The build checker and
independent reviewer use it to verify the retained future Engine entry and
SYCL registration. It also preserves the complete linked-symbol context for
later audits rather than only selected matching lines.

Keep it with the build receipt and source snapshots. Restore this exact log
from Git and verify its receipt hash. It can also be regenerated with
`nm -C --defined-only` against the exact binary named and hashed in
`build-compile-only.json`; a rebuild with different bytes is a new artifact.
Generating this inventory does not invoke the native executable.

Repository hygiene reports this one size warning and zero errors. No evidence
was removed to suppress the warning.
