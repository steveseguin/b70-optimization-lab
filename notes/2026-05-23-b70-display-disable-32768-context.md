# B70 Display Disable And 32768 Context Promotion

Date: 2026-05-23

## Summary

After moving display duty back to the onboard ASPEED VGA adapter and adding
`xe.disable_display=1`, the MiniMax M2.7 INT4 OpenAI-compatible endpoint can
serve a `32768` token context window on the 4x B70 host.

Decision:

- Promote `32768` as the default served context.
- Keep the strict benchmark lane at p512/n1536, context `2048`, for
  apples-to-apples speed comparison.
- Treat `33792` as not reliable for serving on this stack.

## Display / VRAM Change

Kernel command line after reboot:

```text
BOOT_IMAGE=/boot/vmlinuz-6.17.0-29-generic root=UUID=19ad6619-8030-4922-9d5c-ed6e7a6a799f ro quiet splash xe.disable_display=1 vt.handoff=7
```

Boot VGA ownership after reboot:

```text
0000:23:00.0 B70 boot_vga=0
0000:27:00.0 B70 boot_vga=0
0000:43:00.0 B70 boot_vga=0
0000:47:00.0 B70 boot_vga=0
0000:68:00.0 ASPEED boot_vga=1
```

The connected display is now the ASPEED VGA path. B70 display outputs are still
listed by DRM, but they are disconnected and no longer own boot display.

Idle B70 VRAM with vLLM stopped after the reboot:

| GPU | Idle VRAM used |
| --- | ---: |
| 0 | about `135-140 MiB` |
| 1 | about `26 MiB` |
| 2 | about `26 MiB` |
| 3 | about `26 MiB` |

Before the change, GNOME consumed roughly `630 MiB` on B70 GPU 0. Reclaiming
that headroom is enough to move the served context from the old practical
`24576` default to `32768`.

## Context Tests

### 32768

`32768` started successfully with:

```bash
VLLM_MAX_MODEL_LEN=32768 /home/steve/bin/minimax-vllm-serve
```

`/v1/models` reported:

```json
{
  "max_model_len": 32768
}
```

vLLM startup log reported:

```text
Available KV cache memory: 2.02 GiB
GPU KV cache size: 33,792 tokens
Maximum concurrency for 32,768 tokens per request: 1.03x
```

Endpoint checks:

| Check | Result |
| --- | --- |
| Short decode before warmup, p510/n1536 | `60.90 output tok/s` |
| Near-full request, prompt `32408`, output `64` | completed without OOM |
| Near-full request conservative prompt rate | `1625.5 prompt tok/s` |
| Short decode after near-full request, p510/n1536 | `84.12 output tok/s` |

Interpretation:

- The first short decode was cold/compile affected.
- Warm short decode returned to the previous `83-84 output tok/s` band.
- The near-full request proved practical use of the 32k window without an OOM.

### 33792

`33792` was tested because vLLM reported `33,792` GPU KV-cache tokens at the
32k setting. It was not promoted.

Observed behavior:

- The server loaded weights and entered compile/warmup.
- It printed repeated shared-memory broadcast wait messages.
- It did not expose `/v1/models` within the wait window.
- It remained stuck in startup long enough to be treated as unreliable for a
  user-facing default.

Decision: keep `32768`, not `33792`.

## Current Serving Default

Updated wrappers:

- `/home/steve/bin/minimax-vllm-serve`
- `repro/minimax-m27-b70-110tps-ubuntu24-20260523/scripts/06-serve-openai-compatible.sh`

Both now default to:

```text
VLLM_MAX_MODEL_LEN=32768
VLLM_GPU_MEMORY_UTILIZATION=0.95
```

The server is currently running at:

```text
http://10.0.0.65:8000/v1
```

with model:

```text
/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround
```
