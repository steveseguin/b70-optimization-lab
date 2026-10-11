# Evidence retention

Retain all packet sources, receipts, comparisons and the 384 raw layer fixtures.
The packet is approximately 22 MB, below the requested 50 MB limit. The binary
fixtures are consumed directly by the Packet 4/13 exact comparison gate; hashes
alone cannot replace those inputs. No weights, executable binaries or compiler
scratch are committed.

Three files exceed the repository's 1 MiB review threshold, all under
`runs/arithmetic-v1-parallel-20261011/incident-retrospective/`:

| File | Bytes | Value and consumer |
| --- | ---: | --- |
| `timings.jsonl.gz` | 2,832,410 | Every operator's measured wall time; preserves the work included in CPU forward costs and supports future diagnosis. |
| `progress.jsonl.gz` | 1,712,886 | Complete ordered operator trace, rather than only selected successful endpoints. |
| `teardown.json` | 8,808,288 | CPU allocation/owner ledger and verified zero live bytes/in-flight work; read by `compare.py`. This is a CPU mock-owner receipt, not a GPU teardown. |

The two gzip files are deterministic, lossless copies (`mtime=0`). Before
removing their uncompressed working copies, the runner checked each restored
stream's SHA256 against the original bytes. The run's `receipt.json` records
each original byte count and digest under `compressed_logs`. Restore either
with `gzip -dc FILE.gz > FILE` and verify its SHA256 against that receipt.
The teardown JSON remains uncompressed and restores directly from Git.

The cancelled serial pilot remains separate, explicitly incomplete evidence.
Its original numerical producer is retained as `serial-oracle.cpp.txt`; it must
not be treated as complete prompt coverage or a performance headline. Temporary
builds, input manifests/vocabulary, first-layer working outputs and the temporary
required-reading aggregation are removed after validation. The retained
first-layer proof carries the compared bytes and both process receipts.
