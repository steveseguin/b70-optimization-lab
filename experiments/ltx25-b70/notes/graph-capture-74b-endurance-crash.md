# Packet 74b: the two-clip sampler segfaulted on the fourth endurance prompt

*2026-09-17 14:14–14:16 UTC, server PID 4247 (the boot's single server),
120-prompt endurance stream on `pipe-samp2`. No host fault; the process died
with a native segmentation fault.*

Fault-handler stack of the crashing thread (a sampler worker): the
pipelined sampler → `SamplerCustomAdvanced` → `prepare_sampling` → the
resident fast path fell through to ComfyUI's `load_models_gpu` →
`model_load` → `partially_load` → `ModelPatcher.load` → `module.to()`, i.e.
one worker was **moving the transformer's weights** while the other worker
was replaying captured graphs that read them. ComfyUI's loader is not
thread-safe, and the fast path only skips it once the model is fully
resident; on a fresh server both workers' first clips can fall through at
once. Packet 74's 24-prompt run avoided it by timing.

Also seen: while both workers captured their graphs under the exclusive
lock, the server's web loop did not answer HTTP for over a minute (GIL), so
the driver's 60 s poll timed out; polling now retries for up to five
minutes and never retries a submission.

Fix: every fall-through to ComfyUI's loader, and the residency check that
precedes it, now runs under one lock in the fast-path node, so the second
worker sees the first worker's completed load and skips. Packet 76 carries
it together with the encoder shard (packet 75 was never launched).
