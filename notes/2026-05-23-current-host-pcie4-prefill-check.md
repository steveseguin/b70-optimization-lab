# Current Host PCIe4 And Prefill Check

Date: 2026-05-23

## Summary

The fresh Ubuntu 24 serving host is producing about `83.8` output tok/s for
MiniMax M2.7 INT4 AutoRound on the OpenAI-compatible vLLM endpoint. This is
below the older strict `89.314` p512/n1536 promoted lane and below the newer
structured-output `94.406` lane, but the structured-output result is not an
apples-to-apples comparison.

The most likely explanation for the remaining strict-lane gap is PCIe fabric
bandwidth/latency. The current board links the B70s at PCIe4 x16, while the
previous faster host was reported as PCIe5. This is a plausible explanation, not
a final proof, because the current vLLM source also differs from the older
promoted stack.

## Benchmark Context

Current endpoint:

- Model: `/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround`
- Server: `/home/steve/bin/minimax-vllm-serve`
- Host/port: `0.0.0.0:8000`
- Served context: `24576`
- vLLM: `0.20.2rc1.dev2+gc51df4300.d20260523`
- Decode sanity: about `83.78-83.79` output tok/s for prompt 512 / output 1536
- Prompt/prefill sanity: about `1.7k-1.8k prompt tok/s` on long prompt-heavy
  OpenAI-compatible requests

Reference distinctions:

- `94.406 tok/s` was a constrained structured-output lane with regex acceptance,
  short output, and task-specific validation. It should not be compared directly
  against random/free-form p512/n1536 decode.
- `89.314 output tok/s` is the older strict p512/n1536 random decode baseline.
- The current fresh-install serving baseline is therefore roughly `5.5 tok/s`
  below the comparable strict high, not `10+ tok/s` below a comparable lane.

## PCIe Link State

The current host reports card-facing upstream links at PCIe4 x16:

```text
/sys/bus/pci/devices/0000:21:00.0 cur=16.0 GT/s PCIe width=16 max=32.0 GT/s PCIe maxw=16
/sys/bus/pci/devices/0000:25:00.0 cur=16.0 GT/s PCIe width=16 max=32.0 GT/s PCIe maxw=16
/sys/bus/pci/devices/0000:41:00.0 cur=16.0 GT/s PCIe width=16 max=32.0 GT/s PCIe maxw=16
/sys/bus/pci/devices/0000:45:00.0 cur=16.0 GT/s PCIe width=16 max=32.0 GT/s PCIe maxw=16
```

The B70 endpoint functions may still show internal `2.5 GT/s x1` links. This
was also present on the earlier promoted repro manifest and should not be used
by itself to reject the setup.

## XCCL Microbench Results

Artifacts:

- `/mnt/fast-ai/bench-results/collectives/current-pcie4-minimax-shapes-20260523T195501Z.json`
- `/mnt/fast-ai/bench-results/collectives/current-pcie4-allreduce-sweep-20260523T195635Z.txt`

Exact MiniMax-shaped collectives on the current host:

| Mode | Shape | Current mean |
| --- | --- | ---: |
| in-place | Q/K decode FP32 `(1, 2)` | `0.052919 ms` |
| clone | Q/K decode FP32 `(1, 2)` | `0.077376 ms` |
| in-place | hidden decode FP16 `(1, 3072)` | `0.049682 ms` |
| clone | hidden decode FP16 `(1, 3072)` | `0.073742 ms` |
| in-place | hidden profile512 FP16 `(512, 3072)` | `0.232908 ms` |

Older reference from `notes/2026-05-19-minimax-xccl-exact-shape-microbench.md`:

| Mode | Shape | Older mean |
| --- | --- | ---: |
| in-place | Q/K decode FP32 `(1, 2)` | `0.016774 ms` |
| clone | Q/K decode FP32 `(1, 2)` | `0.020703 ms` |
| in-place | hidden decode FP16 `(1, 3072)` | `0.014878 ms` |
| clone | hidden decode FP16 `(1, 3072)` | `0.019358 ms` |
| in-place | hidden profile512 FP16 `(512, 3072)` | `0.117967 ms` |

Broad allreduce sweep:

| Case | Older reference | Current host |
| --- | ---: | ---: |
| 8 bytes | `0.016 ms` | `0.058 ms` |
| 6144 bytes | `0.014 ms` | `0.048 ms` |
| 1 MiB | `0.044 ms` | `0.083 ms` |
| 256 MiB | `9.627 ms`, about `27.88 GB/s` | `19.473 ms`, about `13.79 GB/s` |

The large-message bandwidth is almost exactly half of the older reference. That
is consistent with PCIe4 x16 versus PCIe5 x16 and makes PCIe fabric bandwidth a
credible explanation for most of the current decode gap.

In lay terms:

- The link on this board is running at `16.0 GT/s` per lane.
- A PCIe5 x16 path would run at `32.0 GT/s` per lane.
- Same lane count, half the signaling rate means roughly half the possible
  transfer rate before protocol overheads.
- The measurement follows that expectation: `13.79 / 27.88 = 0.494`, or about
  `49%` of the older bandwidth.
- The old strict decode lane was `89.314 output tok/s`; current warm endpoint
  decode is about `83.8 output tok/s`, or about `94%` of that strict result.
- It is reasonable that a 2x drop in collective bandwidth causes a smaller
  `6%` drop in end-to-end decode, because only part of each token step is
  inter-GPU communication. The rest is local compute, memory access, scheduling,
  and sampling.

This makes PCIe4 a credible cause of the `83` versus `89` strict-lane gap. It
also helps explain why a PCIe5 system could show `89-93` class decode while this
fresh PCIe4 serving host lands around `83` without any quality-reducing change.
The `94` structured lane remains a different benchmark shape and should stay
separately labeled.

## Runtime Drift Caveat

There is also source/runtime drift versus the older promoted result:

- Current vLLM import: `0.20.2rc1.dev2+gc51df4300.d20260523`
- Older promoted engine: `0.20.1-local`
- Current `minimax_m2.py` hash:
  `96e4b81d606cd3a53b974f49a31cbdd8f79cb49704563e91ba7c611e2b0817b4`
- Promoted `minimax_m2.py` hash:
  `14f37797f9e631bf4f8ea1306a9d048d5c6b305c0bffb56cea609faa37c99415`

The repo already documents that even default-off MiniMax branches can alter XPU
compiled graph scheduling. So PCIe is the cleanest current explanation, but a
strict recovery attempt should also retest the exact promoted source patch state
before concluding the whole delta is hardware.

## Prefill Check

Prompt-processing/prefill on the live endpoint is healthy. These were measured
with OpenAI-compatible `/v1/completions`, `max_tokens=1`, `temperature=0`, and
therefore include HTTP overhead plus one generated token. Treat them as
conservative lower bounds for prompt processing.

| Prompt tokens | Warm wall time | Conservative prompt rate |
| ---: | ---: | ---: |
| `510` | `0.317 s` | `1607.9 tok/s` |
| `2036` | `1.163 s` | `1750.1 tok/s` |
| `8144` | `4.450 s` | `1830.3 tok/s` |
| `16288` | `8.997 s` | `1810.3 tok/s` |

Interpretation:

- Prefill is roughly `1.7k-1.8k tok/s` for useful long prompts.
- Long prompts still have visible TTFT, for example about `9 s` for a 16k
  prompt.
- Keep `max_num_batched_tokens=512` for the stable serving recipe. Repo notes
  show that 1024-token prefill chunks previously triggered Intel `ocloc`/IGC
  failures, so larger chunks are not yet a safe default.

## Warm Versus Cold

Warm and cold rates should be labeled separately. Cold runs can include model
load, graph capture, kernel compilation, and cache creation. Warm runs reuse
more of that state and are the fairer comparison for steady service.

Known examples:

- Older repro first post-reboot pass: `69.33 output tok/s`.
- Older repro immediate warm rerun: `88.72 output tok/s`.
- Current 24k endpoint warm short-decode checks: about `83.78-83.79 output
  tok/s`.

For user-facing claims, report warm serving throughput and separately mention
that first-run compile/cache behavior can be much lower.

## Operational Note

The server was stopped briefly to run the XCCL microbench, then restarted with
`/home/steve/bin/minimax-vllm-serve`. After restart, `/v1/models` reported
`max_model_len=24576`, and a small `/v1/completions` smoke request succeeded.
