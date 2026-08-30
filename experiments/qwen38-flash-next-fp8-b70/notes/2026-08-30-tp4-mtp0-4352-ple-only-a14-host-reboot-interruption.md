# Qwen3.8 Flash-Next FP8 TP4 MTP0 A14 host-reboot interruption

Date: 2026-08-30
Status: infrastructure-interrupted before model load; no model result

A14 passed storage, source, staged-runtime, four-card discovery, and four-rank
collective preflight. It started a new server on port 19686, but the host then
became unavailable and rebooted while workers were entering distributed
initialization. The last server record is rank 0 initialization. No checkpoint
shard, PLE offload receipt, healthy endpoint, client request, output, quality
gate, or timing row exists.

The previous boot journal contains no orderly shutdown and no model/runtime
exception at the boundary. This is therefore an infrastructure interruption,
not evidence for or against the deterministic QSA treatment. It cannot satisfy
the fresh-server requirement and receives no performance or quality credit.

After reboot, all four expected B70s rediscovered below 43 MiB with no owned
process or listener. The external NTFS evidence drive did not auto-mount; it
was mounted read-write at its documented path before the partial evidence was
inspected. The existing A14 directory is retained and will not be reused.

The admissible successor is a new attempt identity with the exact A14 model,
source, placement, cache, prompts, authority hashes, and full battery. No
protected result changed.

Structured receipt:
[`../data/20260830-tp4-mtp0-4352-ple-only-a14-host-reboot-interruption.json`](../data/20260830-tp4-mtp0-4352-ple-only-a14-host-reboot-interruption.json).
