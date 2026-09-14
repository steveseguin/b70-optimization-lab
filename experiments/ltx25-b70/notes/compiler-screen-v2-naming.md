# Fresh compiler campaign naming, 2026-09-14

The frozen `run-compiler-screen.py` hardcodes `compiler-screen-01`, whose failed
incident evidence must remain intact. The separate
`scripts/run-compiler-screen-v2.py` requires `--campaign`, validates a bounded
lowercase filename identifier, and passes that name explicitly into the existing
nine-request schedule and retention paths. It has no default campaign name.
Existing output/capture collisions still fail before any request.

All numerical, graph, server, runtime, source, compiler, comparison, fault and
retention gates remain unchanged. The v2 client still uses the original pinned
`compare-clip.py`; it does not integrate the new streaming comparator. The
original compiler client and all its frozen dependencies remain unchanged.

Five standard-library tests passed in `data/compiler-screen-v2-cpu-01/receipt.json`.
They execute only extracted naming/parser/schedule ASTs, never import the client.
The full new module AST equals the original after reversing only the declared
naming and CLI changes. Other checks cover required arguments/default refusal,
unsafe names, the unchanged nine request cases, and all frozen helper hashes.
The receipt contains the exact parsed CLI and generated request names. No client,
native runtime, GPU request, server action or host-setting change was executed.

The original source snapshot and exact diff are preserved in
`data/compiler-screen-v2-cpu-01/run-compiler-screen.original.py` and
`data/compiler-screen-v2-cpu-01/campaign-naming-only.patch`.

- Original client SHA256: `51376640d128bfeac5bb6e76e40ce2d7bdb44a610e9e649f9aef9a0dcfc069e6`
- New client SHA256: `0069bee68b70230ce9ae17774873e497cc62573fe945c5f666ac1fd4e9884d33`
- Test SHA256: `6dbaeadd05aa0ece102f9a785bd870dcfc9f3e9409e56d65a96534e02c3f299f`
- Receipt SHA256: `e07650bcbaf40ec41b6d0ee7ed6bce59dd9e76b23e32f58652490855c6be1469`

Prepared invocation, only after root-owned recovery admission and verification
of the single persistent server and its new identity:

```bash
/home/steve/.venvs/ltx25-baseline/bin/python -B \
  /home/steve/llm-optimizations/experiments/ltx25-b70/scripts/run-compiler-screen-v2.py \
  --campaign compiler-screen-02 \
  --packet /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-compiler-03 \
  --manifest-sha256 9ecd5f9863289e00a934c1f4f400582092f37d0ee92035512fc095773ad02980 \
  --server-run /mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-server-compiler-03
```

The server-run name is an explicit proposed fresh identity, not a claim that a
server has launched. Its final path must match the owning launch receipt. The
client itself performs no start, stop, restart or retry. This change provides
fresh evidence names only; it makes no native correctness or speed claim.
