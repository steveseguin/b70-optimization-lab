# Official f01e AutoRound TP1 E4M3-KV 8K sentinel R1

Status: **preregistered and executable; not launched**.

This is a one-dose reopen of the least-compounded E4M3 KV-cache question:
AutoRound Qwen3.8 27B, TP1, MTP0, graph explicitly off, one exact 8K request,
then the complete frozen text-quality battery. It uses one GPU and one server
lifetime. It does not run graph, another TP, another MTP depth, or another
context depth.

The older immutable `e9d1398d9` nightly booted this cell and measured about
`24.1009 tok/s`, but only 3/25 outputs matched either oracle (3/20 in the
stable subset). That result is capacity-only and output-divergent. It closed
all compounded E4M3 descendants. The current official f01e image is materially
different—vLLM `0.27.2rc1.dev77+gac7509e2b.xpu` at `ac7509e2b`, versus
`0.26.1rc1.dev1102+ge9d1398d9`—so it justifies this sentinel, not an assumption
that E4M3 numerics have been fixed.

The server identity matches the already successful f01e AutoRound F16 block
except for two explicit deltas: `--kv-cache-dtype fp8_e4m3` and
`--enforce-eager`. The runner requires the exact image ID, source commit,
package versions, AutoRound startup marker, eager marker, E4M3 KV marker, no
graph-capture marker, direct model verification, clean pushed `main`, frozen
input hashes, fresh ext4 output/cache roots, an idle host, a fresh port, and
the canonical GPU campaign lock.

The exact 8K receipt has 128 generated tokens and 99 decode intervals. The
same server then runs seven exact cases, eight repeat checks, the 8K needle,
24 frozen-baseline comparisons, and cache-zero checks. Only both gates green
produce `passed-quality-clean-sentinel`. If exact 8K passes but quality fails,
the speed is retained only as quarantined diagnostic evidence and descendants
remain closed. `unsupported` requires an explicit exact-image log line naming
the E4M3 KV dtype and unsupported/invalid semantics; a timeout or generic
startup failure remains `failed`.

No speed floor applies. Neither this result nor a failure may lower, replace,
or relabel the protected F16 graph/eager results or the prior E4M3 observation.
Even a full pass authorizes only a separately preregistered expansion packet.

Static validation and inert plan:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp1-e4m3kv-8k-sentinel-r1.sh --check
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp1-e4m3kv-8k-sentinel-r1.sh --plan
```

GPU execution, only after confirming the host remains idle:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp1-e4m3kv-8k-sentinel-r1.sh \
  --execute \
  --ack 'RUN qwen38-official-f01e-autoround-tp1-e4m3kv-8k-sentinel-20260826-r1'
```

The runner has global EXIT/INT/TERM cleanup for the exact container and strict
postflight checks for the container, port, model-server process, and render
node. All raw output is additive evidence under a fresh campaign identity.
