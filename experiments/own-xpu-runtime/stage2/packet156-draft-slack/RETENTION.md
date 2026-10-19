# Retained evidence

Keep all packet156 files. This packet retains the complete packet154 smoke and
five-view bracket input/report plus both raw timing streams for all 12 prompts
per view, compressed independently with deterministic gzip. No event or
outlier is filtered from retained input. Each bound's `inputs` array binds
the original path, raw size/hash and compressed size/hash. The bound rows
add request, command sequence, op, position, actual host endpoints, clipping
and the generous credited time.

`replay_retained.py` verifies both hashes, decompresses each receipt into a
temporary directory, and reproduces the complete original split and every
new bound row. It does not depend on mutable raw runs in sibling packets.
`method/packet154_analyze.py` is the original analyzer, copied without changes.
Source snapshots are gzip files to preserve original bytes without creating
misleading executable trees or broken Markdown navigation. Their manifest is
`evidence/source-pins.json`.

Any artifact above 1 MiB is retained because it is a complete, hash-bound
report/input or a full per-window analysis needed to audit the rejection;
the final `evidence/storage.json` lists these artifacts. Large JSON must not be
replaced with a hand-selected subset. The compressed receipts allow exact
restoration without model weights, device jobs, historical binaries or
compiler caches. No old evidence was removed or archived by this task.
