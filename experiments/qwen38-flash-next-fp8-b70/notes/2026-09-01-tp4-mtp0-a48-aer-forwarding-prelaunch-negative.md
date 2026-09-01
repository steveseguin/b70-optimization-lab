# Qwen3.8 Flash-Next FP8 A48 AER-forwarding prelaunch negative

Date: 2026-09-01
Status: procedural negative; zero model or inference credit

The corrected A48 privileged preflight passed and established numeric local
NVMe/root-port AER baselines. The supervisor received both values, created its
diagnostic-only evidence directory, and passed its initial pressure sample.
Its clean `env -i` child launch did not explicitly forward those values to the
server wrapper, which failed closed with:

```text
FAIL: A48 requires numeric host-control AER baselines
```

No run, cache, compile, or RPC directory was created. No model process,
checkpoint shard, endpoint, or request existed. The supervisor captured clean
four-device postflight and the root wrapper restored swap and ASPM. The
diagnostic evidence is retained at:

```text
/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-fullgraph-mtp0-2304-ple-only-r1-attempt48-supervisor
```

A49 is the exact path-only successor. It explicitly passes the two already
validated numeric baselines through the supervisor's clean environment; model,
runtime, graph, collective, placement, prompt, quality, and authority identity
are unchanged.
