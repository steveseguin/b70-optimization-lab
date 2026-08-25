# Embedded-MTP Q8/q8_0-KV TP1 SYCL-graph exact-depth R1 preregistration

This sealed create-only packet fills the seven embedded-MTP Q8_0 artifact,
TP1/MTP0, q8_0-KV graph cells at exact active contexts 0/2K/4K/8K/16K/24K/32K.

It mechanically overlays the passed embedded-MTP F16 graph runner. The only
runtime selector delta is `-ctk q8_0`, `-ctv q8_0`, and `selectors.kv=q8_0`;
campaign and output root are distinct lifecycle identities. The model remains
the pinned MTP-bearing artifact `5cb35eb...` / `9408dcb3...`, with MTP disabled.
Source, build, backend, 32-DSO closure, graph cache 8, three-patch chain,
optimization environment, verbose argv, contexts, and phase-aware gates are
unchanged.

The accepted graph-off `q36-mtpq8-tp1-kv-q8-context` result is checksum-bound
for identity/workload comparison only. Every graph cell must pass the existing
ordered prefill/decode evidence policy. Prefill may be mixed partial when cache
8 fills; decode must replay all requests without cache-full, compatibility
rejection, unsupported-device, update, or recreate events.

Default invocation is inert. `--check` is CPU/static only, and execution
requires the exact acknowledgement. A pass remains seven raw cells with quality
pending; it cannot publish, submit records, replace protected graph-off values,
or alter featured speeds.
