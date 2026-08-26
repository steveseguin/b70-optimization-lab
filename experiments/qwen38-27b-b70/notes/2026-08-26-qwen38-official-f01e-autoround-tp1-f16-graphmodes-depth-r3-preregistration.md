# Official f01e AutoRound TP1 F16 graph-mode depth block R3

Status: **preregistered and executable; not launched**.

R1 is preserved as an aborted prelaunch attempt. A live-origin mismatch was
raised inside command substitution, but the runner's deliberate lack of global
`set -e` allowed it to create its evidence/cache roots and begin model
verification. It was interrupted during the sixth of seven model shards. No
container or GPU service launched. R2 adds an explicit failure-propagation gate
and used fresh campaign, output, cache, container, and port identities.

R2 then proved both eager and PIECEWISE server identities and passed both full
quality batteries, but its depth helper calls omitted the required
`--context-capacity` argument. All twelve helper invocations exited before
sending a request, so R2 authorizes no depth cells. R3 adds only
`--context-capacity 32896` and again uses fresh campaign, output, cache,
container, and port identities.

This is the next high-value AutoRound coverage block after the official-FP8
fit/depth work. It measures the twelve missing Qwen3.8 AutoRound TP1/MTP0/F16
cells for graph off and PIECEWISE at exact active contexts 2K, 4K, 8K, 16K,
24K, and 32K. The already measured b2dd FULL_AND_PIECEWISE/F16 curve remains a
separate dated profile and is neither rerun nor replaced.

The runtime is the locally resident immutable official image
`vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f`
with vLLM `0.27.2rc1.dev77+gac7509e2b.xpu` at commit
`ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9` and XPU kernels `0.1.12.3`.
Weights remain the revision-pinned `devan-carlin/Qwen3.8-27B-int4-AutoRound`
artifact already used by the lab.

The two arms are deliberately independent and sequential. Each gets a fresh
ext4 compile cache, one server lifetime, six exact token-ID depth requests,
and the complete text-quality battery against the frozen baseline. Graph off
is explicit `--enforce-eager`. PIECEWISE uses capture size one and must prove
the PIECEWISE capture markers while proving no FULL decode capture marker.

There is no speed floor. A slower correct measurement is retained as additive
evidence and cannot lower a protected speed. If an exact depth request passes
but the cross-profile quality battery does not, its receipt remains a real
screened measurement for review rather than disappearing; it is not promoted
as fully quality-qualified. Context zero stays missing.

The older nightly already showed E4M3 output divergence and hard-refused E5M2
on XPU. Those 36 cells are not bundled blindly into this run. The materially
newer f01e runtime may reopen them, but only through the already implied low-
dose gates: eager E4M3 at 8K plus quality first, and E5M2 init/canary first.
This packet therefore spends two server lifetimes on the twelve F16 cells most
likely to produce publishable coverage.

Static validation and an inert plan:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp1-f16-graphmodes-depth-r3.sh --check
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp1-f16-graphmodes-depth-r3.sh --plan
```

GPU execution, only after the current campaign is terminal and the host is
idle:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp1-f16-graphmodes-depth-r3.sh \
  --execute \
  --ack 'RUN qwen38-official-f01e-autoround-tp1-f16-graphmodes-depth-20260826-r3'
```

The runner requires a clean pushed `main`, exact frozen hashes, exact local
image and model verification, unused roots, free ports, no container/model
server/render owner, and the canonical GPU lifecycle lock. Cleanup is strict
between arms and after the terminal receipt.
