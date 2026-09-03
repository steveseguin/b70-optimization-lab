# R183: with torch.compile off the depth-2 phantom is gone (published R156, async scheduling on)

Date: 2026-09-03 18:59-19:06 EDT, boot 88f0984f (clean). R156 image unchanged, `--enforce-eager`
(`CompilationMode.NONE` in the resolved config), depth 2, async on. Prereg
`data/2026-09-03-qwen38-fp8-r156-mtp2-phantom-enforce-eager-r183-prereg.json`. Results:
`/mnt/fast-ai/bench-results/qwen38-fp8-r156-mtp2-phantom-enforce-eager-20260903-r183/query-mtp1/`.

## Result

`phantom_first_token_rows: []`. Ten rows differ from the compiled-graph MTP0 oracle, all mid-sequence
(rollback-c010 @97, index-c017 @49, evidence-c023 @52, index-c033 @33, cache-c040 @60, index-c041 @46,
monitoring-c044 @84, evidence-c047 @85, rollback-c050 @60, evidence-c063 @88; first token 271 on every row), i.e.
the tie-class prompts under eager numerics, not phantoms.

Prereg branch: "phantom absent under eager -> the defect is in the compiled graph".

## Where this leaves the depth-2 phantom

Established today: not a KV/GDN page (R180), not layer 0 or its kernel (R181), not the attention metadata
(R182: correct and async-independent), needs the unsplit VLLM_COMPILE graph (R182a/b: any per-layer split removes
it), needs torch.compile at all (R183), needs async scheduling (R169). The lane's compilation config is
`cudagraph_mode=PIECEWISE, cudagraph_capture_sizes=[1]` with a deterministic Inductor config, so two knobs remain:
the size-1 piecewise XPU graph capture (static buffers replayed for single-sequence decode steps, including the
discarded async extra step of the previous request) and Inductor's buffer planning across the compiled pieces.
R184 runs both as one chain on R156: (a) `cudagraph_mode=NONE`, (b) `allow_buffer_reuse=false` with graphs kept.
