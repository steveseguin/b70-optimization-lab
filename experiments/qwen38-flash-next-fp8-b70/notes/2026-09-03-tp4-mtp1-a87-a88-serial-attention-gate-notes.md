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

## A88 answer and A89

A88 came up and passed its canary with no diagnostic line at all, not even
the single-row one: the flag was in the API server's environment but not
in the engine core's or the workers' (`/proc/<pid>/environ`). vLLM forwards
only registered `VLLM_*` variables to those processes (the mkldnn flag
works because 805cde59 registered it in `envs.py`). Overlay `0a03a84c`
registers `VLLM_XPU_FA_SERIAL_SPEC_DECODE` in `envs.py` and reads it
through `envs` in the attention gate; A88 was stopped after its canary.
A89 is the A88 packet at attempt 89 / port 19761 on that head
(`tools/rewrite-q38-a88-to-a89-registered-flag.py`); same battery and
pins. The "reached" marker is the first thing to look for.
