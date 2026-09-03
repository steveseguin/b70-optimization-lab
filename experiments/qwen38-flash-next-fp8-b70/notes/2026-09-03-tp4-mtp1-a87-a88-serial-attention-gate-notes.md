# A87 observation and A88 preregistration: the serial-attention gate did not fire

Date: 2026-09-03

A87 (A85 plus overlay `d3a61403`, `VLLM_XPU_FA_SERIAL_SPEC_DECODE=1`
exported and present in the server environment) came up, captured its
graph, passed the exact canary and ran the battery, but the port's
"reached" marker never printed: none of graph capture, the canary, or the
requests entered the serial branch, so A87 measures the A85 identity again
(its rows are recorded as an A85 repeat in the A87 data file).

A88 is the A87 packet at attempt 88 / port 19760 on overlay `53d6594b`,
which adds one warning per process just before the gate printing every
clause the gate tests (`max_seqlen_q`, dynamic causal, mask mods,
`num_actual_tokens`, `cu_seqlens_q`, `seqused_k`, FA version) whenever the
flag is set and a multi-row batch arrives, and a second one-time line when
only single-row batches are seen. Its battery is the same; the point is the
diagnostic line. Generator `tools/rewrite-q38-a87-to-a88-fa-diag.py`.
