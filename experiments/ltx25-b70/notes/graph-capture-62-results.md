# Packet 62: the upsampler node's cost is model management, not the model; host froze mid-campaign

*2026-09-17 03:10–03:14 UTC, server PID 11951, boot `a8b906bc…`. Evidence:
[`data/graph-capture-62/`](../data/graph-capture-62/). The host locked up
silently at about 03:14 UTC during the fourth arm; the two boots after it
locked up idle (23:40 and 23:48 EDT) with nothing running; the user restarted
at 00:11 EDT. Files the server had not flushed came back as zero bytes; the
`f62-up` summary below is rebuilt from the per-prompt histories' server
timestamps, and the fourth arm's receipts were lost.*

| Arm | Prompts | Distinct | Exact | Steady interval | Note |
| --- | ---: | ---: | --- | ---: | --- |
| warm clip (`pipe`, boat) | 1 | 1 | yes | — | captures |
| `pipe-upphase` (phase-timed upsampler node) | 12 | 11 | **11/11** | 2.547 s | diagnostic syncs added |
| `pipe-up` (captured upsampler forward) | 20 | 19 | **19/19** | **2.529 s** | no gain vs `pipe` 2.519 s |
| `pipe-up-save` (save-behind) | 9 of 20 done | — | receipts zeroed by the freeze | — | server log shows 2.18–2.48 s per prompt; inconclusive |
| `pipe` control | not reached | | | | |

## Where the upsampler node's time goes

Per-phase, synchronised wall time inside a drop-in of the sealed node (12
clips, same calls in the same order):

| Phase | mean s |
| --- | ---: |
| `model_management.load_models_gpu([upscale_model])` | **0.0677** |
| latent to model device | 0.0003 |
| `un_normalize` (VAE stats on xpu:3 pulled to xpu:0) | 0.0014 |
| `LatentUpsampler.forward` | 0.0238 |
| `normalize` | 0.0004 |
| to intermediate device (CPU) | 0.0009 |
| **node phases total** | **0.0945** |

So the model is a quarter of the node and ComfyUI's model-management call is
nearly three quarters, for a model that is already fully resident. That call
is not a check: `load_models_gpu` detaches and re-runs `model_load` for a
resident model, walks its module list, queries allocator statistics on the
device, and may call `empty_cache`. The two sampler nodes make the same call
for the 42 GB transformer before every sampling pass. Capturing the
upsampler's forward was therefore never going to move the interval, and it
did not: 2.529 s against 2.519 s.

**Next exact lever:** a resident fast path that skips the whole bookkeeping
when every requested model is already fully loaded (no arithmetic involved),
measured first in a timed mode that records what each call costs today.

## The freeze

No fault, no kernel line: the server's last log line is a normal
"Prompt executed in 2.18 seconds", the campaign log ends mid-arm, and the
journal continues with cron noise for 26 minutes before the boot ends. This
is the same silent-lockup class as the previous three. The two subsequent
idle-boot lockups are new evidence that the platform itself is unstable
independent of the LTX workload.
