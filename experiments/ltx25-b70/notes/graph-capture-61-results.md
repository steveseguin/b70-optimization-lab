# Packet 61: the latent upsampler's forward is 0.025 s; the node's 0.24 s is elsewhere

*2026-09-17 02:58–03:00 UTC, server PID 4523, boot `a8b906bc…` (after the
user-confirmed reboot and the boot-03 health admission). Evidence:
[`data/graph-capture-61/`](../data/graph-capture-61/).*

| Arm | Prompts | Distinct clips | Exact | Steady interval |
| --- | ---: | ---: | --- | ---: |
| warm clip, `pipe` graph (boat) | 1 | 1 | yes | 74.2 s preview (captures) |
| `pipe-uptime` (eager upsampler, synchronised timing) | 12 | 11 (+1 fill) | **11/11** | 2.486 s |
| `pipe-up` (captured upsampler) | — | — | — | not run: gate refused a `timed`→`graph` switch without a restore, and that refusal is sticky for the server |

## The measurement that matters

`LatentUpsampler.forward` on the real [1, 128, 4, 8, 8] bf16 latent, wall
time with a device sync before and after, 11 calls on xpu:0:

| | seconds |
| --- | ---: |
| mean | **0.0251** |
| median | 0.0233 |
| min / max | 0.0211 / 0.0347 |

Opus's per-node table put node 348 at **0.240 s**. The model forward is a
tenth of that. The rest of the node is, in order of execution
(`comfy_extras/nodes_lt_upsampler.py`): `model_management.load_models_gpu`
with a 98 MB request on a card holding 21 resident transformer blocks and
their graph pools; the latent copy to the model device; `un_normalize` and
`normalize`, each pulling the VAE's per-channel buffers from xpu:3 to xpu:0
(the VAE lives on the fourth card in this placement); and the final
`.to(intermediate_device())`, a synchronous copy to the CPU that the next
node immediately copies back. Which of these costs the 0.21 s is not yet
measured; a phase-timed drop-in of the same node (same calls, timers between
them) is the next arm. Graph-capturing the forward is worth at most 0.025 s
and is no longer the lever for this node.

## Runner defect, recorded

The upsampler gate refused to switch from `timed` to `graph` without an
intervening `restored` run, and its failure latch is per-server. The runner
issued no restore. Every remaining arm carries the gate node, so server 61
cannot run further arms; the fix is in the gate (switching modes restores
first, recorded in the receipt), and the packet-62 runner sequences arms so
the point is moot.

Server 61 stays up until packet 62 is ready; one graceful stop precedes the
next launch. No fault, no retry.
