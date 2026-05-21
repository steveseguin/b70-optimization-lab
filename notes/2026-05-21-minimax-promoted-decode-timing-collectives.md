# MiniMax M2.7 Promoted Decode Timing: Collectives Still Dominate - 2026-05-21

## Goal

Run a low-overhead decode timing probe on the restored promoted MiniMax M2.7 AutoRound INT4 runtime after the rejected Q/K AR+apply candidate was removed. The goal was to check whether remaining decode overhead comes from CPU callback/output handling or from GPU collective boundaries.

Diagnostic flags added on top of `repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh`:

```bash
VLLM_XPU_DECODE_TIMING=1
VLLM_XPU_DECODE_TIMING_RANK=0
VLLM_XPU_DECODE_TIMING_SKIP_FIRST=16
VLLM_XPU_DECODE_TIMING_PRINT_EVERY=0
VLLM_XPU_DECODE_TIMING_SYNC=0
```

This was a timing probe, not a publishable benchmark. `SYNC=0` keeps the run close to normal throughput, but the per-region timings should be read as relative attribution rather than exact GPU kernel duration.

## Result

- Model: `/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround`
- Hardware: 4x Intel Arc Pro B70 32GB
- Engine: vLLM XPU, TP4, llm-scaler WS INT4 path
- Prompt source: vLLM random text
- Prompt/output: 512 prompt tokens, 512 output tokens
- Warmup/measured: 1 warmup, 1 measured repeat
- Decode throughput: `95.88318068980547` tok/s
- Total throughput: `191.76636137961094` tok/s
- Token SHA256: `4130d4a9e926047ef17d94ec800ac3022349051e938f03d1fe37d659bfdded67`

Largest rank-0 timing buckets:

- `all_reduce:(2, 3072):torch.float16`: `1287.646412 ms` total, `234` calls, `5.502762 ms` average
- `all_reduce:(1, 3072):torch.float16`: `742.056593 ms` total, `359` calls, `2.067010 ms` average
- `all_reduce:(2, 2):torch.float32`: `594.895557 ms` total, `108` calls, `5.508292 ms` average
- `all_reduce:(1, 2):torch.float32`: `440.745060 ms` total, `170` calls, `2.592618 ms` average
- `logits.local_argmax_lm_head`: `64.196575 ms` total, `1010` calls, `0.063561 ms` average
- `all_reduce:(512, 3072):torch.float16`: `17.618818 ms` total, `359` calls, `0.049077 ms` average
- `all_reduce:(512, 2):torch.float32`: `6.660277 ms` total, `170` calls, `0.039178 ms` average
- `gpu_model_runner.async_output_tolist`: `2.168739 ms` total, `1008` calls, `0.002152 ms` average

## Interpretation

The output callback path is not the current limiter. The measured `async_output_tolist` cost is tiny compared with the hidden-state and Q/K variance collective buckets.

The next optimization work should stay focused on math-preserving collective boundaries:

- FP16 hidden-state all-reduce shapes `(1 or 2, 3072)`, likely split across attention `o_proj`, MoE output, and final residual/norm paths.
- FP32 Q/K variance all-reduce shapes `(1 or 2, 2)`.
- Graph/collective scheduling around those operations, rather than framework output callback minimization.

The promoted quality posture remains unchanged: the restored promoted runtime passed the strict quality gate immediately before this timing probe, and this diagnostic only enabled timing instrumentation.

## Artifacts

- Result JSON: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/decode-timing-promoted-20260521T024008Z/minimax-promoted-decode-timing-vllm-random-text-p512n512.json`
- Log: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/decode-timing-promoted-20260521T024008Z/minimax-promoted-decode-timing-vllm-random-text-p512n512.log`
- Summary data: `data/minimax-m27-promoted-decode-timing-collectives-20260521.json`
