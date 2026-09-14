# Short-context prefill: 4B, 9B, 27B INT4 and FP8

Completed September 13, 2026 on `steve-TURIND8-2L2T` (two ASRock B70s). All four models were measured at concurrency one. The allocation experiment preserved every tested output and did not meaningfully change decode speed, but delivered only small gains on 4B/9B and none on 27B. **Keep the existing serving defaults.**

The [summary](../data/2026-09-13-short-prefill/summary.json) is complete; `promotion_qualified=false` is intentional. This was one loaded server per model with an off/on/off comparison, not an independent-process qualification or a new decode record. The [preregistration](2026-09-13-short-prefill-prereg.md) fixes the workload and gates.

## Measurements

Each control value below averages the two off-mode controls. Within each arm, take the median of three repeats per prompt class, then the median across prose, code and documentation. Inputs are exact numeric token IDs at 128/256/512 tokens, output cap 128 with `ignore_eos`, capacity/budget 1024, one sequence, and prefix caching disabled. These repeated/truncated continuation shapes are diagnostic; the separate full realistic suite supplies the quality and decode checks.

Server prefill is vLLM’s interval from first scheduled execution to its first token, obtained from a one-request histogram delta. It includes runtime work and is **not isolated GPU kernel throughput**. HTTP TTFT additionally includes dispatch, draft/stream delivery and transport. The [source definition](../data/2026-09-13-short-prefill/vllm-prefill-metric-definition.txt) is preserved.

| Model / profile | Prompt tokens | Server prefill ms | Input tokens/s | HTTP TTFT ms |
| --- | ---: | ---: | ---: | ---: |
| 4B W4A16 · TP1 · MTP3 | 128 | 48.76 | 2625 | 50.28 |
| 4B W4A16 · TP1 · MTP3 | 256 | 75.37 | 3397 | 76.96 |
| 4B W4A16 · TP1 · MTP3 | 512 | 129.89 | 3942 | 131.65 |
| 9B W4A16 · TP1 · MTP3 | 128 | 70.47 | 1816 | 76.82 |
| 9B W4A16 · TP1 · MTP3 | 256 | 114.96 | 2227 | 121.34 |
| 9B W4A16 · TP1 · MTP3 | 512 | 207.56 | 2467 | 209.52 |
| 27B INT4 · TP2 · MTP4 | 128 | 78.28 | 1635 | 93.45 |
| 27B INT4 · TP2 · MTP4 | 256 | 126.09 | 2030 | 139.97 |
| 27B INT4 · TP2 · MTP4 | 512 | 232.92 | 2198 | 247.81 |
| 27B FP8 · TP2 · MTP1 | 128 | 76.62 | 1671 | 98.78 |
| 27B FP8 · TP2 · MTP1 | 256 | 106.72 | 2399 | 129.27 |
| 27B FP8 · TP2 · MTP1 | 512 | 177.49 | 2885 | 200.56 |

## Optimization result

The existing FP16 custom op computes 32-row linear pieces and concatenates their outputs. The candidate preallocates the output and writes each identically sized GEMM into its destination slice. It preserves the small-row decode branch, bias handling, precision and chunk dimensions. A 72-case operator screen across representative model shapes, mixed/zero inputs and repeated executions found zero bit differences. Operator gains were roughly 1–5%; they did not transfer uniformly to the endpoint.

| Profile | Prefill throughput change vs two controls | Strict decode control → candidate | Decode change | Full-output parity |
| --- | ---: | ---: | ---: | --- |
| 4B W4A16 · TP1 · MTP3 | +3.02% | 191.33 → 190.76 tok/s | -0.30% | 12/12 |
| 9B W4A16 · TP1 · MTP3 | +2.11% | 123.46 → 123.30 tok/s | -0.13% | 12/12 |
| 27B INT4 · TP2 · MTP4 | -0.13% | 117.12 → 116.98 tok/s | -0.12% | 12/12 |
| 27B FP8 · TP2 · MTP1 | -0.16% | 54.95 → 54.85 tok/s | -0.17% | 12/12 |

Prefill change is the median across lengths of per-prompt candidate/mean-control throughput ratios. The 4B result only narrowly clears the preregistered 3% screening threshold; its largest observed control drift was 1.31%. The 9B result is below that threshold. Both 27B results are neutral. All remain unpromoted because there is no independent-process candidate repeat. No default launcher, public image, package or performance headline was replaced.

All 324 measured prefill requests reported zero cached tokens and matched their repeated/off/on/off numeric outputs. Each model also passed two complete 12-prompt natural-completion suites under the 512-token response cap, canaries, and 12/12 candidate-versus-control full-token comparison. Every new control matched its original qualified R308 or R304 outputs, another 12/12 per model. The collector rechecks those original files against their preserved hashes; it does not trust a success label alone. Strict decode uses the conventional 99 numeric-token intervals between output tokens 1 and 100, balanced over the six realistic prompt classes. SSE bursts retain their shared arrival timestamps.

## Runtime and replay

4B/9B use a default-off overlay of public R308 `sha256:b9bbb5190f6dd47973501e61aa129706c92345b310eeec4537a20256eba424ba`; both 27B profiles use public R304 `sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2`. The other 16 tracked runtime files match each respective parent. Modified `utils.py` is `e81491d119ada4e9e27f2ae97811dcfc1df61753114547c2306dc49d9fec055c`. Controls execute the original allocation branch through this disabled experimental dispatcher, rather than an unmodified parent process. V1 runner, FP16 activations/native KV, CLASSPAD0 and the original graph/speculation settings are retained.

The experimental images are local research artifacts: `prefill/r308-direct-out` (`196fde0b9da51…`) and `prefill/r304-direct-out` (`5063526f426b…`). Parent contracts and complete overlay identities are in the [packet](../data/2026-09-13-short-prefill/). The kernel image was not rebuilt or changed for this experiment.

Source:

- [Operator probe](../probes/prefill-rowchunk-out-probe.py), [opt-in patch](../probes/patch-prefill-rowchunk-out.py), [Dockerfile](../probes/Dockerfile.prefill-direct-out).
- [Client](../scripts/bench-short-prefill.py) and [single-profile controller](../scripts/run-short-prefill-stage.py). The controller takes `--profile`, `--out`, `--port`, `--image`, `--image-id`, `--runtime-sha256`, and `--base-contract-receipt`; it uses host-local model paths. Each invocation owns one server only, switches the candidate through its private cache-directory flag, runs both full strict suites, removes the flag, and performs cleanup/postflight.
- [Collector](../scripts/summarize-short-prefill.py) and [deterministic evidence exporter](../scripts/export-short-prefill-evidence.py).

Review without GPUs:

```bash
replay_dir=$(mktemp -d /tmp/qwen-prefill-review.XXXXXX)
for archive in experiments/qwen38-27b-b70/data/2026-09-13-short-prefill/evidence/*.tar.gz; do
  tar -xzf "$archive" -C "$replay_dir"
done
python3 experiments/qwen38-27b-b70/scripts/summarize-short-prefill.py \
  --raw-root "$replay_dir" --out "$replay_dir/recomputed-summary.json"
```

The evidence manifest binds every archive and individual receipt, including raw SSE, requests, before/after metrics, launch/runtime identity, original references, strict outputs, and health logs. Compilation caches and model weights are excluded. Full originating-host data remains at `/mnt/fast-ai/bench-results/qwen-short-prefill-20260913`.

All four stages ended with clean two-card compute/XCCL and journal postflights. All servers are stopped and the optimization flags removed. No power, swap, cache-drop, driver or reboot changes were made. One 27B preflight encountered TCP port reuse before any model process started; that receipt is preserved, a separate port was used, and the controller now distinguishes TIME_WAIT from an active listener.
