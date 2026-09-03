# R182: a per-layer trace op in the compiled graph removes the depth-2 phantom (and flips 10 tie rows)

Date: 2026-09-03 18:30-18:52 EDT, boot 88f0984f (clean). Prereg
`data/2026-09-03-qwen38-fp8-r156-mtp2-phantom-layer-trace-r182-prereg.json`.

## Three builds to get a probe that fires

- v1 (`sha256:9ec2d18a...`) and v2 (`sha256:a34e55a6...`) put plain Python `logger.info` calls in
  `Qwen3NextModel.forward` (v1 gated on the row count, v2 on the GDN metadata). Both servers were healthy and emitted
  nothing: this lane runs `CompilationMode.VLLM_COMPILE` (mode 3; the `mode: None` in the CLI args line is the
  unresolved default), and Dynamo traces the Python away. Aborted after one request each (17 minutes lost).
- v3 (`sha256:4a3e5d43...`, `docker/r182-layer-trace-v3.py`) registers a custom op
  `vllm.qwen_r182_layer_trace_xpu` (eager body, fake impl, `mutates_args=["tensor"]`, the R110 technique) and calls
  it at embed, after every decoder layer (hidden and residual) and after the final norm, for prefill batches of
  <= 4 sequences. 130 lines per forward per rank, with the full-attention metadata attached at layers 3, 7, ..., 63.
  Note for CPU-side import tests: the container's WORKDIR is a source checkout that shadows site-packages for bare
  `python -c`; run with `-w /` to import the /opt/venv copy the server uses.

## R182a (async on, the phantom configuration): no phantom, 10 tie flips

`/mnt/fast-ai/bench-results/qwen38-fp8-r156-mtp2-phantom-layer-trace-20260903-r182/query-mtp1/query.json`:
`phantom_first_token_rows: []`, and 10 rows differ from the MTP0 oracle: cache-c000, evidence-c007,
capacity-c014, index-c017, index-c025, index-c033, index-c041, monitoring-c044, evidence-c047, evidence-c063.
cache-c000 is the R67 exact FP16 tie; evidence-c007/index-c033/evidence-c047/evidence-c063 are the recurring
large-M miss set of R175/R179. So the probe is not observation-neutral: a mutating custom op after every layer
splits the VLLM_COMPILE graph at every layer boundary, changes Inductor fusion/buffer planning, perturbs ULPs on
the tie-class prompts, and removes the phantom on cache-c032 for the first time with async scheduling on.

## Reading

The phantom depends on the compiled graph's structure, not on any custom kernel (R181: the GDN kernel's layer-0
output is identical in phantom and clean runs) and not on KV/GDN pages (R180). The remaining mechanism is inside
the Inductor-compiled pieces of the prefill graph under async scheduling: buffer reuse or an in-place mutation
across the async step boundary. R183 tests it directly: published R156, depth 2, async on, `--enforce-eager`.
R182b (probe image, async off) runs as the control of the probe image itself.

## R182b (async off, same probe image, 18:52-18:59): identical to R182a

Same 10 tie-class rows differ from the MTP0 oracle (all mid-sequence, indices 5-96, first token 271 on every
row), no phantom. The per-layer traces of all 64 prefills are equal between R182a and R182b on both ranks: embed,
every layer's hidden and residual last-row sums, every full-attention layer's metadata (seq_lens, query_start_loc,
block table, slot mapping) and the final norm (`compare-r182.py`: "requests with any divergence: []"). On the
split graph, async scheduling has no observable effect on the prefill forward. The phantom needs the unsplit
VLLM_COMPILE graph; the metadata the attention layers receive for request 33 is correct in both runs.
