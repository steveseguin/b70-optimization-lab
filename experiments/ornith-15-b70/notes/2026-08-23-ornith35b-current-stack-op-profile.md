# Ornith 1.5 35B-A3B: current-stack decode profile

Date: 2026-08-23 EDT

Status: **diagnostic ranking only; not throughput evidence**

The seven-stage accepted stack was rebuilt with temporary queue profiling and
barriers around every logical SYCL graph-loop iteration. The barriers
intentionally serialize work, include dispatch overhead, and can charge an
otherwise skipped graph node for queue bookkeeping. Therefore no value below
is converted into a projected tok/s gain.

After discarding cold weight-reorder work, the third warmed one-token graph
contained 1,203 timed logical rows. Dense `MUL_MAT` work ranked first at
`5032.174 us`; routed `MUL_MAT_ID` work ranked second at `2042.292 us`. The
largest repeated projection families were the already-fused routed gate/up
path (`1165.625 us`), routed down (`876.667 us`), recurrent QKV (`844.060 us`),
and router logits (`651.975 us`). The single full-vocabulary output head was
`705.208 us`.

The next bounded candidate is routed down plus its exact weighting/reduction
tail. In this diagnostic those three existing stages ranked as:

- routed down: `876.667 us` across 40 layers;
- expert-weight multiply: `217.289 us` across 40 layers;
- accepted ordered reduction: `200.313 us` across 40 layers.

This is not the earlier rejected candidate, which moved multiplication into a
separate reduction kernel and changed generation. A new attempt may proceed
only if each tuned Q4_K dot product is rounded exactly, each expert product is
rounded exactly, and the eight products are added in the original order. It
must pass the same-binary exact-output gate before any speed test.

Structured values are in
`../data/2026-08-23-ornith35b-current-stack-op-timing-summary.json`; the
compressed raw log is beside it. The temporary profiler is not part of the
published package.
