# Recurrent output-Q8 and convolution fusion result

Three additional default-off SYCL boundaries were implemented and matched on
the real Qwen graph:

1. `GGML_SYCL_FUSE_GDN_EPILOGUE=1` now directly produces standard or reordered
   Q8_1 for the following output MMVQ from GDN output RMSNorm, learned weight,
   SiLU(z), and multiply. It reuses skipped scratch, tracks the logical MMVQ
   consumer, and composes with MMVQ+ADD. Runtime diagnostics confirmed 48/48
   recurrent matches and direct-consumption counters through 64.
2. `GGML_SYCL_FUSE_SSM_CONV_CACHE=1` commits recurrent convolution snapshots
   directly from SSM_CONV and skips the matched CPY nodes, including MTP
   rollback slots. Runtime counters confirmed continuous real-model matches.
3. `GGML_SYCL_FUSE_SSM_CONV_QK_NORM=1` combines SSM_CONV, SiLU, and Q/K L2
   normalization while preserving the shared V input. It matches the real
   `conv_output_raw` graph, but showed no useful isolated speed signal.

All paths compile in JIT and AOT. The existing focused M=1/M=4 fusion suite
passes 8/8 after integration, strict suite runs pass with cached tokens zero,
and short deterministic semantic smokes remain correct.

The important measurement lesson is that the initial JIT signal did not carry
to AOT. JIT strict crossovers suggested the output-Q8 path was about `+4.15%`
and conv cache about `+1.61%`. The required AOT crossovers measured:

- output-Q8 only: `49.9784 tok/s` versus `49.4856 tok/s`, only `+1.00%`;
- output-Q8 plus conv cache: `49.4181 tok/s` versus `49.9691 tok/s`, `-1.10%`.

The isolated output-Q8 lane is directionally positive but below the 3% promote
gate; conv cache becomes a loss in the combined AOT stack. Keep all three
flags default off. The current strict headline remains the earlier direct-GDN-
cache stack at about `50.390 tok/s`; no result approached 68 tok/s.

Artifacts are the `mtp3-jit-fusion3-*`, `mtp3-jit-epicache-*`,
`mtp3-aot-newstack-*`, and `mtp3-aot-epiq8-*` JSON files under
`data/qwen36-27b-mtp-gguf-q4-b70-baselines/`.
