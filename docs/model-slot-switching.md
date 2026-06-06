# Single Model Slot Switching

This host should normally run one large model at a time. The public LAN API can
stay stable while the backend model changes.

Public endpoint:

```text
http://<server-lan-ip>:8000/v1
```

Backend slot:

```text
127.0.0.1:18080
```

The frontdoor is OpenAI-compatible and has no bearer-token requirement. It
limits concurrent generation requests according to the active model profile.

## Why One Slot

Four B70s can run a large model well, but two large vLLM backends at once would
fight for VRAM, compile cache, device handles, and port `8000`. The model-slot
setup makes the intended behavior explicit:

- stop the current backend;
- load exactly one selected profile;
- restart the same LAN frontdoor;
- keep clients pointed at the same base URL.

## Install Once

```bash
cd /home/steve/llm-optimizations
scripts/install-vllm-model-slot-service.sh --profile minimax-m27-c1
```

Install, enable at boot, and immediately move to the slot-managed MiniMax
profile:

```bash
cd /home/steve/llm-optimizations
scripts/install-vllm-model-slot-service.sh --profile minimax-m27-c1 --start
```

This installs:

```text
/etc/systemd/system/b70-vllm-slot.service
/etc/systemd/system/b70-openai-frontdoor.service
/etc/b70-vllm-slot/current.env
```

Tracked source files:

```text
deploy/systemd/b70-vllm-slot.service
deploy/systemd/b70-openai-frontdoor.service
configs/model-slots/*.env
scripts/serve-vllm-profile.sh
scripts/run-openai-frontdoor-profile.sh
scripts/switch-vllm-model-slot.sh
```

## Switch Models

List available profiles:

```bash
scripts/switch-vllm-model-slot.sh list
```

Switch back to the known-good MiniMax profile:

```bash
scripts/switch-vllm-model-slot.sh switch minimax-m27-c1
```

Try the documented text-only Qwen FP8 candidate after its weights are present:

```bash
scripts/switch-vllm-model-slot.sh switch qwen36-27b-fp8-vrfai
```

Try the first image+text candidate:

```bash
scripts/switch-vllm-model-slot.sh switch qwen3-vl-30b-a3b-fp8
```

The switch command stops the generic slot services and the older
MiniMax-specific services before starting the selected slot. This avoids two
large models being loaded at the same time. It also disables the older
MiniMax-specific units when the generic slot is activated, so reboot behavior
stays single-model.

## Current Profiles

| Profile | Status | Modalities | Purpose |
| --- | --- | --- | --- |
| `minimax-m27-c1` | production | text | Current known-good MiniMax M2.7 INT4 AutoRound endpoint, 32K context, one active generation. |
| `qwen36-27b-fp8-vrfai` | experimental | text | Validated as a 4K text concurrency profile with an XPU BF16 fallback for the failing native FP8 linear path. Useful for c16/c32 throughput tests. |
| `qwen36-35b-a3b-fp8` | research | text | Interesting Qwen3.6 35B-A3B FP8 text candidate. Needs local validation. |
| `qwen3-vl-30b-a3b-fp8` | research | text,image | First multimodal image+text candidate. Needs startup, image, quality, and concurrency validation. |

## Check Status

```bash
scripts/switch-vllm-model-slot.sh status
curl http://127.0.0.1:8000/status
curl http://127.0.0.1:8000/v1/models
```

The frontdoor status includes the active profile metadata:

```json
{
  "model_slot": {
    "name": "minimax-m27-c1",
    "modalities": "text",
    "status": "production"
  },
  "frontdoor": {
    "auth": "none",
    "max_active_generations": 1
  }
}
```

## Validation Gate For A New Profile

Do not call a new profile production-ready until it passes:

1. `/v1/models` reports the expected model and context length.
2. A text completion returns valid tokens.
3. For VL profiles, `/v1/chat/completions` accepts a real image request.
4. Short decode throughput is measured after warmup.
5. 16K and 32K prompt TTFT are measured.
6. c2/c4 concurrency tests report both throughput and latency.
7. Quality smoke tests pass with the same sampling settings used for service.

## Notes On The Candidate Models

`qwen36-27b-fp8-vrfai` is text-only, but it is the most grounded Qwen slot
because earlier lab work already validated the 4x B70 TP4 layout. Prior notes
reported about `45.9` output tok/s without speculation and about `48.1` output
tok/s with n-gram speculation at 512/512, with `max_model_len=32768`.

On 2026-06-06, the native compressed-tensors FP8 path failed during profiling on
this host with `RuntimeError: could not set scales primitive attribute` in
`torch.ops._xpu_C.fp8_gemm_w8a16`. The validated workaround is the opt-in
`VLLM_XPU_FP8_LINEAR_BF16_FALLBACK=1` patch captured in
`patches/vllm-xpu-qwen-fp8-bf16-fallback-20260606.patch`. This fallback is
slower than native FP8 but avoids the failing primitive without reducing the
stored checkpoint precision.

Current Qwen fallback measurements used `max_model_len=4096`, about `2071`
prompt tokens per request, and `512` generated tokens:

| Concurrency | Aggregate output tok/s, wall | Mean request decode tok/s | Mean TTFT |
| ---: | ---: | ---: | ---: |
| 1 | `20.48` | `20.91` | `0.51 s` |
| 16 | `243.01` | `17.73` | `4.48 s` |
| 32 | `402.51` | `16.21` | `8.21 s` |
| 64 | `556.55` | `12.57` | `15.65 s` |

Use c16 for more interactive latency, c32 for a practical aggregate-throughput
profile, and c64 only when high total throughput matters more than TTFT. Full
details are in `notes/2026-06-06-qwen36-fp8-bf16-fallback-concurrency.md`.

`qwen3-vl-30b-a3b-fp8` is the right first multimodal slot because it directly
supports image+text. Expect higher TTFT on image prompts because the vision
encoder and image preprocessing are part of the request path.

`qwen36-35b-a3b-fp8` should be treated as a quality/performance comparison
after the 27B text slot and 30B VL slot are operational.
