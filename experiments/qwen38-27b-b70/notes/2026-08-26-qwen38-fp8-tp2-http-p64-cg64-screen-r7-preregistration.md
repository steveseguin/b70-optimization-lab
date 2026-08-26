# Qwen3.8 official FP8 TP2 p64 size-64 graph screen R7

Status: **preregistered diagnostic; not launched**.

The qualified p64 service captures only the size-one PIECEWISE decode graph;
its c64 work therefore is not the explicitly captured size. R7 adds an exact
size-64 capture while retaining size one. It changes no model, quantization,
TP topology, KV format, generation method, scheduler capacity, cache policy,
prompt, or output length.

One fresh server measures only c64 against the frozen 64-row output oracle.
The server log must prove that both requested graph sizes were captured.
Every response must return 128 raw token IDs, use zero cached prompt tokens,
avoid every cross-base oracle collision, and leave a clean
container/process/port state.

The qualified control is `695.792088 tok/s`; the candidate is promising only
at or above `730.581692 tok/s` (5%). A successful one-server screen is still
not publishable and requires two new confirmation servers. Startup, capture,
device, output-gate, or cleanup failure closes this exact graph shape unless a
materially different mechanism is introduced. No value is interpolated or
extrapolated.

See the [machine-readable contract](../data/2026-08-26-qwen38-fp8-tp2-http-p64-cg64-screen-r7-prereg.json).
