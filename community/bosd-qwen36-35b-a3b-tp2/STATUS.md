# Qwen3.6-35B-A3B GPTQ-Int4 — dual-B70 vLLM-XPU TP2: the `0.31.0-b1-experimental` image clears the post-init APIServer hang

## Classification

| Field | Value |
| --- | --- |
| Evidence level | `community-reported` — contributor measurement on contributor hardware; not reproduced in the reference lab |
| Patch review status | no patch; stock `intel/llm-scaler-vllm` image, only the tag changed (`1.5` → `0.31.0-b1-experimental`) |
| Tested in reference lab | no |
| Safe to merge as documentation | yes |
| Eligible for `repro/` or `results/` | no until `B70-tested` |

## Maintainer Review (2026-11-22)

Maintainer section, added after merging [PR #86](https://github.com/steveseguin/b70-optimization-lab/pull/86).
The contributor's text below is unchanged.

| Field | Value |
| --- | --- |
| Evidence level | `community-reported` (unchanged) |
| Patch review status | read, no execution |
| Tested in reference lab | no; blocked by model identity and local infrastructure, not tested and failed |
| Claims entry | none; the model has no accepted identity (see below) |

**Checked here:**
- All four files were read in full. The launcher starts a public Intel image with the model mounted read-only.
  It downloads and runs nothing else. No secrets, tokens or LAN identifiers.
- The LocalMaxxing link resolves (HTTP 200). Its contents were not compared with this entry.
- The arithmetic:
  - In every row of the ThreadPool table, per-stream = aggregate / concurrency, to the rounding shown.
  - At concurrency 24 to 96, the `lmx` aggregates are 2.0-6.0 % below the ThreadPool ones.
  - The `lmx` p50 latencies agree with its own aggregates (256 x concurrency / p50) within 3 %.

**Not run here, and why:**
- **Model identity.** The model is a local GPTQ-Int4 export with no source repo, revision, quantization recipe
  or file hashes (`README.md:50`). Under `AGENTS.md`, another GPTQ checkpoint would not be the same comparison.
- **Images.** Neither image is on the reference host (19.7 GB each), and both are identified only by tag, not by
  digest (`README.md:48`).
- **Host.** The reference host has 15 GiB of host RAM. The contributor reports that the two workers stage about
  20.8 GiB of shards each. The host's B70s were also serving another model, which is loaded only at boot.
- **No lab evidence either way on `1.5`.** The lab has no record of `intel/llm-scaler-vllm:1.5` on B70. Its
  `B70-tested` vLLM TP2 entries used `0.21.0-b1` (`dominick253-qwen36-27b-fp8-tp2-docker`) and a pinned digest
  (`dominick253-qwen36-35b-fp8-b2-tp2`).

**Known issues found in review:**
1. **The single-stream figure conflicts with the contributor's own second measurement.**
   - The ThreadPool sweep gives 10.6 tok/s at concurrency 1 (`README.md:96`, `reported/bench.txt:9`).
   - `lmx` gives 16.1 tok/s at concurrency 1 (`reported/bench.txt:26`), and its 15.9 s p50 for 256 tokens
     (`reported/bench.txt:29`) is the same 16.1 tok/s.
   - The ThreadPool per-stream rate is also higher at concurrency 24 (16.6) than at 1 (10.6).
   - So "single-stream ~10.6 tok/s, TP2 communication overhead" (`README.md:35`, and the Claim and Known Issues sections below)
     is not supported as stated. The ThreadPool concurrency-1 row may include a cold first request.
2. **Unexplained marks.** The `(23/24)`, `(46/48)` and `(62/64)` marks in `reported/bench.txt:26` are not
   explained. If they count completed requests, those aggregates cover fewer streams than the column heading.
3. **Summary, not raw output.** `reported/bench.txt` is titled raw output but is a summary. Two latency cells are
   truncated (`17.x`, `21.x`), and there is no client script, JSON or server log.
4. **Host-specific card mask.** `vllm-qwen36-35b-a3b-tp2.sh:22` hard-codes `ZE_AFFINITY_MASK=1,2`, because the
   contributor's B60 is device 0. A host with only two B70s needs `0,1`, and the script does not let the
   environment override it. The container also runs `--privileged`.

**Needed to raise the evidence level:**
- the model's source and revision, or its quantization recipe and file hashes;
- image digests for both tags;
- the client script with its JSON output;
- the `1.5` server log around the hang;
- an explanation of the concurrency-1 row and the `(n/m)` marks.

```text
Contribution: llm-scaler-vllm 0.31.0-b1-experimental serves dual-B70 TP2 Qwen3.6-35B-A3B GPTQ-Int4 where 1.5
              hangs after engine init; aggregate throughput sweep to concurrency 96
Contributor: bosd (https://github.com/bosd)
Status: acknowledged
Validated effect: not measured
Evidence: community/bosd-qwen36-35b-a3b-tp2/
Included in: none
```

## Provenance

- Contributor: bosd
- Hardware: ASRock TRX50 workstation, Threadripper 9960X, 2× Intel Arc Pro B70 (32 GB) + 1× Arc Pro B60 (24 GB, idle for this run), Fedora 44, kernel `7.3.4`, `xe` driver, compute-runtime/level-zero `26.35.39758.21`.
- Right-to-submit statement present: yes — all runs are the contributor's own on the contributor's hardware.
- Third-party material and attribution: Intel llm-scaler-vLLM image (`intel/llm-scaler-vllm:0.31.0-b1-experimental`) and vLLM / vLLM-XPU; `Qwen3.6-35B-A3B` from the Qwen team (locally GPTQ-Int4 exported). CCL environment is the community `vllm#41663` recipe.

## Claim

For dual-B70 vLLM-XPU TP2 serving of Qwen3.6-35B-A3B GPTQ-Int4, image
`0.31.0-b1-experimental` (vLLM `0.31.0+xpu.llmscaler`) serves where `1.5`
(vLLM `0.26.1`) completes engine init and then hangs the APIServer; measured
aggregate throughput scales near-linearly to concurrency 64 and peaks at
**~1268 tok/s at concurrency 96** (single-stream ~10.6 tok/s). Contributor
measurement, not a reference-lab finding.

## Contributor Environment

| Field | Value |
| --- | --- |
| GPU model / count / VRAM | 2× Intel Arc Pro B70 (Battlemage), 32 GB each; `ZE_AFFINITY_MASK=1,2` |
| OS / kernel | Fedora 44 / `7.3.4` |
| GPU driver / level-zero | `xe`; compute-runtime / level-zero `26.35.39758.21` |
| Engine / image | `docker.io/intel/llm-scaler-vllm:0.31.0-b1-experimental` (Docker Hub 2026-10-12, 19.7 GB on disk) |
| vLLM version | `0.31.0+xpu.llmscaler` (server banner); the hanging `1.5` image reports `0.26.1.dev0+g568afb3a1` |
| Model / revision | `Qwen3.6-35B-A3B`, local GPTQ-Int4 export (`qwen3_5_moe` / GatedDeltaNet hybrid MoE, 256 experts, ~A3B active) |
| Quantization | weights GPTQ-Int4 (`XPUwNa16LinearKernel` / auto_gptq); KV auto (fp16); dtype float16 |
| Command / env | `community/bosd-qwen36-35b-a3b-tp2/vllm-qwen36-35b-a3b-tp2.sh`; CCL env = `vllm#41663` (`CCL_ENABLE_SYCL_KERNELS=0`, `CCL_ATL_TRANSPORT=ofi`, `CCL_ZE_IPC_EXCHANGE=pidfd`, …), `--tensor-parallel-size 2 --distributed-executor-backend mp --enforce-eager` |
| Prompt / output / context / concurrency | ~45-token prompt, 256 output tokens (`ignore_eos`), `--max-model-len 8192`; concurrency 1/24/48/64/96 |
| Cache / speculation | prefix caching off; no speculative decoding; `--enforce-eager` |
| Metric / repeats / TTFT | wall-clock aggregate completion-tokens/s via client ThreadPool; corroborated by `lmx speed-test matrix run` (benchVersion 0.7.7); no TTFT breakdown from the ThreadPool arm |
| Logs / durable links | `reported/bench.txt`; LocalMaxxing matrix https://www.localmaxxing.com/en/inference-benchmarks/cmwsasd8k008vqh01im51npfg |

## Reference Lab Environment

Not run. No reference-lab reproduction for this entry.

## What Was Actually Run Here

All on the contributor host. On `0.31.0-b1-experimental`: engine init ~60 s,
`Application startup complete`, `/health` → 200, `/v1/models` → `tp2-test`, then
a client ThreadPool decode sweep at concurrency 1/24/48/64/96 and an independent
`lmx speed-test matrix run` (submitted to LocalMaxxing). On `1.5`, the identical
command: engine init completes (`init engine ... took 60.60 s`) then the
APIServer prints nothing and `/health` stays `000`. Nothing was run in a
reference lab.

## Findings

Confirmed on the contributor host:

- Image, not flags. The post-init APIServer hang on `1.5` is reproducible and
  independent of port (8000 vs 8001), GPU contention (both B70s free), and
  `VLLM_ENABLE_V1_MULTIPROCESSING=0`. The only change that produces a live
  endpoint is the image tag → `0.31.0-b1-experimental`. This is a vLLM v1
  frontend / EngineCore-handshake behavior that differs between the two image
  builds, not a tunable on `1.5`.
- Aggregate throughput scales near-linearly to concurrency 64; the knee is
  ~64–96; single-stream is below a single-card Int4 decode of the same family
  (expected TP2 communication overhead).
- Host-RAM gating (not silicon): with 62 GB host RAM, two TP2 workers staging
  ~20.8 GiB shards each OOM unless the other single-card GPU services are
  stopped first.

Hypothesis (not isolated): the differing behavior is a specific vLLM-XPU v1
frontend fix between 0.26.1 and 0.31.0; the exact commit was not bisected.

## Known Issues

- `--shm-size` must not be combined with `--ipc host` (they conflict).
- Single-stream decode (~10.6 tok/s) is slower than a single B70 Int4 decode of
  the same family — TP2's value here is aggregate throughput and fitting a model
  too large to prefer on one card, not latency.
- No formal quality eval; outputs were coherent on a generic prompt only.

## Open Questions For The Contributor

1. Which vLLM-XPU commit between 0.26.1 and 0.31.0 fixes the APIServer-start
   hang (bisect not done).
2. Throughput via vLLM's own `benchmark_serving` (TTFT/ITL distribution) rather
   than a client ThreadPool.
3. Behavior at higher `--max-model-len` and with prefix caching on.

## Disposition

`community-reported`. A first live dual-B70 TP2 serving datapoint for this model
on the contributor hardware, with a concrete image-version finding that others
on B70 TP2 can test directly by swapping only the tag. Raising the evidence
level needs a reference-lab (or matching-hardware) reproduction of both the
`1.5` hang and the `0.31.0-b1-experimental` endpoint.
