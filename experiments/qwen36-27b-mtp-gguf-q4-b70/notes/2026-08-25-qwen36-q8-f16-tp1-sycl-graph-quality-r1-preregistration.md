# Qwen3.6 target-Q8/F16 TP1 SYCL-graph quality R1

This is the shortest complete quality path for the passed seven-cell curve: one
fresh isolated `llama-server` boot on the exact curve source, build, model,
F16-KV, graph-on, and cache-8 environment. It runs the existing Qwen3.6 battery
with all four objective canaries, eight identical greedy repeats, and a 31,744-
token needle under a 32,768-token service capacity. All 13 requests must report
`cached_tokens=0`, and the server must show positive graph capture and replay
with no compatibility rejection or unsupported-device evidence.

One battery can legally cover all seven curve cells. Model, quantization, TP,
MTP, KV, source, build, runtime environment, and graph cache do not vary across
the cells; the curve already supplies separate mechanism evidence at every
depth, and the near-32K needle bounds the shorter contexts. Per-depth duplicate
quality batteries would add no new selector coverage. This does not transfer to
another KV type, graph mode, TP, MTP, model artifact, source, or build.

The source overlay is frozen in order: evidence port `1a8589f8...`, pointer-
stable Q8 memo `1575acc5...`, and capacity-scaled memo `3def9e5e...`. The
quality server has its own sealed 33-entry effective DSO closure; it is not the
llama-bench closure.

Claim boundaries remain narrow. The seven speeds are raw-engine measurements,
not HTTP serving rates. At depths above zero, prefill remains mixed/partial when
the curve reports cache-full; quality passing cannot relabel that as fully graph
captured. The packet cannot publish, submit, replace protected graph-off values,
or alter historical speeds.
