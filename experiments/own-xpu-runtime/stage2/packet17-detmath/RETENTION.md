# Evidence and restoration

Keep the exact independent checks, source snapshots, table, receipts and oracle
fixtures. These are numerical evidence, not cache material. No weights are
copied into this packet. `rope.bf16` is a 512 KiB pinned model-constant table.
The generated constexpr header and compiled binaries stay in ignored build/.

`evidence/host-hashes.txt.gz` losslessly stores every ordered exp/log hash row
(2^32 encodings each; 32,768 rows at 262,144 inputs/chunk). Its uncompressed
SHA-256 and compressed SHA-256 are recorded in host-hashes-receipt.json. The
source snapshot there is the exact version used for the measured host pass;
later census changes affect device coverage pilots, labels and card selection,
not the host-hash arithmetic. `evidence/fixture-inputs.bin.gz` preserves all
130,573 distinct native elementary inputs evaluated by the v1 fixtures; the
uncompressed digest is in fixture-trace-receipt.json. Compression was checked
by re-reading decompressed bytes and re-hashing before accepting it.

The CPU oracle run under
`../../../qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/`
retains 384 BF16 layer files, all token/top-five rows, input identity and
losslessly compressed verbose logs. Any log archive at least 1 MiB is retained
because it binds every runtime site to the actual run and preserves timing and
failure evidence. The run receipt records original verbose-log bytes and hashes;
the runner verifies decompressed equality before removing only those originals.
Do not delete or consolidate BF16 fixtures based on similarity alone.

Rebuild with WINDOW.md's CPU commands. Hash archives can be restored to the
named ignored build paths with Python gzip, validating their original hashes.
The device receipts bind actual built binaries and inputs. A rebuild must create
a new seal; old receipts do not admit different binaries. No device window is
admitted by archive restoration alone. Temporary trace instrumentation, input
preparation and test scratch may be removed after verified evidence retention;
the ignored build's native binaries, hash rows, table and expected fixtures
remain required for the prepared coordinator windows.

## Final oracle large-artifact review

The following files are retained as original run evidence. Restore their exact
bytes from Git; for `.gz` files, the run receipt also provides the decompressed
SHA-256. The consumers are the oracle review and future failure/state comparisons.
`teardown.json` records allocation ownership and retirement across the complete
run, so it is evidence that the graph retired correctly, not temporary scratch.

| Artifact (relative to the oracle run) | Bytes | SHA-256 |
| --- | ---: | --- |
| `incident-retrospective/progress.jsonl.gz` | 1712886 | `2cde3378959d5f78b4585f398d5c5883b5c7dd8d79cb165ad9d5e0140f94a3f3` |
| `incident-retrospective/teardown.json` | 8808288 | `14171f0e51bfbedfe4c1cd96513aa986e5910141840cbd0193eacb224b247fa0` |
| `incident-retrospective/timings.jsonl.gz` | 2774144 | `d55761cce785db2527bc9e94f17e1901c03adad654b897305a39363dbf817c19` |
