# Large inherited inputs

These exact files close the copied packet124c build and selection provenance.
They are retained unchanged; size or duplicate content is not a reason to
discard an input. Restore from the same relative path in frozen
`../packet124c-record-bundle`, then verify SHA-256 below. `copy131.json` records
the complete original copy and preserved symlink targets. Compiler outputs
and caches remain ignored under `build/` and are rebuilt by `build131.py`.

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `rope.bf16` | 4,194,304 | `92a8f39204b5b8b1969ee2e5d3caac2310ced502bfeb9f51380b537d451ef390` |
| `lineage-inputs/fusion-rope.hpp` | 12,582,900 | `1bbb9d0ff339bd4ed20f02505aeaef484d906e8162d20ea247bae3889ecd7428` |
| `lineage-inputs/packet103-composition-selection.json` | 1,993,365 | `a88d65c9c93be5a8b677f6c221c798e2c95ea91ed85971f774a8ef4bdd2685e8` |
