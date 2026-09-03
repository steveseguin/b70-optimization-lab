# Qwen3.8 Flash-Next FP8 A84 preregistration: logprob probe of the MTP1 path at depth

Date: 2026-09-03

A81 (MTP1 in the full decode graph) and A83 (eager MTP1) both produced the
exact-2K continuation `460b0d5c...`, not the MTP0 line's `afffd211...`, so
the speculative verification path is a different function from single-row
decode at depth regardless of graph replay. A84 is the A81 server at attempt
84 / port 19756 (`tools/rewrite-q38-a81-to-a84-logprob-probe.py`, fresh
paths only; packet launcher `2ef62cd0...`, client `413ad156...`, supervisor
`2488b6be...`, host wrapper `b7cd7bea...`) driven by the A59 logprob probe
at depths 8, 256 and 2048 (eight first-step repeats, three 128-token
repeats). Offline, its top-5 first-step logprobs and per-token logprobs are
compared with the MTP0 line's A76/A77 probes at the same depths.

Reading: the depth at which the first-step top-1 logprob first differs and
by how much (numeric-noise scale, about 1e-3 nats, versus a structural gap)
locates the divergence in prefill-side state handling versus the two-row
verify step, and bounds how close a serial-exact fix must get. The probe's
own repeat check also tells whether the MTP1 path is repeatable on its own
server (A81 and A83 suggest it is).
