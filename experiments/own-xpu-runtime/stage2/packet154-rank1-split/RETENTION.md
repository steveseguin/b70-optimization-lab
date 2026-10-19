# Packet154 retention

Retain the vendored source closure, the packet136 compiler command provenance,
and build/vendor-objects. These exact objects (about 46 MB total) close the
incremental link without depending on mutable parents. They are intentional
build evidence, including members over 1 MiB. Their source paths, copied paths
and SHA256 values are in evidence/vendor-objects.json and immutable-binaries.json.
Restore missing tracked objects with Git; do not silently relink against a parent.
The native source closure remains available for rebuilding, and engine-commands
records the exact incremental compiler/link invocations.

Generated CPU fixture directories are bounded test scratch. Device evidence,
when separately authorized, is budgeted at 145 MB per view and retained without
inventing outputs. Do not delete earlier packet evidence or consolidate archives
as part of this packet. Build products must remain below 300 MB.
