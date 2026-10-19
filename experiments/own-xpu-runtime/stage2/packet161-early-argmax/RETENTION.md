# Packet161 retained evidence

`evidence/hidden.bf16.gz` is 1,572,904 bytes, above the 1 MiB review threshold.
Retain it: it contains all 385 actual final head inputs (320 reconstructed
target, 65 saved native draft) as lossless BF16 bytes, allowing the costly
bound scan to be reproduced without rerunning a model or relying on external
hidden-state paths. Uncompressed shape is `[385,2560]`, 1,971,200 bytes.
`preparation.json` binds its uncompressed SHA256; `positions.json` gives every
original source path/hash, corpus, oracle top-five values or draft winner.
This is unique measurement input, not a generated cache or model weight copy.

Restore with standard gzip decompression. Target source streams remain under
the packet49 external oracle tree and packet132's pinned originals; packet132
also retains verified per-document archives under `evidence/capture/`.
No originals were moved or deleted. Reconstruct via `prepare.py` using those
hash-bound sources and the pinned existing CPU math bridge. `analyze.py` needs
only this retained head-input file, positions, and the admitted GGUF head rows.
The GGUF is not committed; every read range is hashed in preparation/analysis
receipts. The source decoder, head arithmetic and original runtime remain in
their frozen packets.

Keep both failed CPU draft entries, their actual argv, logs, failure and
teardown receipts. The first entry lacked the native loader's idle-I/O flag;
the second exhausted its fixed address-space cap and released all allocations.
Neither produced independent draft hidden inputs. There is no disposable model
cache or build output in this packet. `fractions.csv` keeps every position and
both target partitions; summaries are not substitutes for it.
