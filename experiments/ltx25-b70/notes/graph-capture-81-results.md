# Servers 79b, 80, 81: the sharded encoder's one-NaN-clip race (2026-09-19)

Each server ran the sharded arm (two encode workers, 24 layers on xpu:2 and 24
on xpu:3, two-clip sampler) and stopped on its second or third distinct clip:

| Server | Clips exact before the stop | Failing clip | Symptom |
| --- | --- | --- | --- |
| 79b | boat, marble (oracle passed) | bird (51002) | preview MP4 muxer EINVAL (audio) |
| 80 | boat | marble (61001) | block 0 capture proof "inert" |
| 81 | boat, marble (sha equal to references) | bird (71002) | all four tensors NaN (evidence `output/validation/f81-tsh-05`) |

Server 81's evidence explains the other two: NaN latents make the muxer
reject the audio, and NaN block inputs make the perturbation proof read
equal (NaN == NaN bitwise), i.e. "inert". The failing prompt and thread vary
across servers, so this is a race, not arithmetic. Every clip that was the
first encode on its worker thread (captured under a full device synchronize)
was bit-exact; failures are later replays on that thread.

Cause found in the encode path: a worker thread ran the encoder's eager parts
(embedding lookup, norms, projection, the parent loop's clones) on the
device's default stream, while the layer graph replays and the pinned-host
staged copies ran on the thread's own streams. Nothing ordered the two, so a
replay could read a half-written input. Packet 82 runs the whole worker
encode inside the thread's per-device stream contexts.

Side findings: the shard installs cleanly (10.9 GB on xpu:3), decoder
placement is all on xpu:3, ComfyUI's loaded-model table is as designed, and
sampler stage times of 1.8-4.0 s per clip with two clips in flight were
observed while the encoder was still the pacing stage.
