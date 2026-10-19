# Private CPU rehearsal tools

Shared `ops/` is frozen. These copies retain its CPU sandbox and real report execution.
Only the synthetic half/sibling fixtures, private import paths, and pause-aware CPU deadlines differ.
`launch_env.py` is byte-identical to the shared authority.

Upstream identities (historical provenance, not mutable runtime source pins):

- `experiments/own-xpu-runtime/ops/rehearse_entry.py`: `c413c15fc68b7feff90459598674a701b0026449d9aec433fe5892f68b5ee596`
- `experiments/own-xpu-runtime/ops/entry_sandbox.py`: `caa50117358c7258293305ffaf13a16902c03ee29a19019dfc5114c307a62386`
- `experiments/own-xpu-runtime/ops/launch_env.py`: `a55f31e6052e33d5b4702b01eddd4e5af5c4029fda6fc452dd8f564f3dfdc364`

The packet uses its private `ops/rehearse_entry.py --report`; it does not modify the shared helper. `v5/aux_gates.py` also executes the unchanged shared `ops/launch_env.py` with the private pause-aware sandbox.
