# Qwen3.8 Flash-Next FP8 A79 preregistration: load the model from the local NVMe copy

Date: 2026-09-03
Status: frozen before launch; iteration-speed diagnostic with the full frozen
client as its equality gate

## Why

Every deterministic-line attempt loads the 173 GB checkpoint from the USB
copy (`/mnt/usb-models`, ntfs-3g over a 10 Gb/s link): 541-550 s of the
about 14.5 minutes from launch to ready (A73, A77). A verified copy of the
same tree exists on the root NVMe (`/mnt/fast-ai/llm-models/...`); the lane
moved off it during the root-NVMe corrected-error storm, which the BIOS
2.4a update cleared at Gen4. On 2026-09-03 the NVMe copy was re-verified
against its 2026-08-27 receipt (`verify-model.py`, status pass, 124 s for
the whole tree). Loading from it should remove most of the 550 s.

## Design

`tools/rewrite-q38-a78-to-a79-nvme-model.py` derives A79 from the frozen A78
packet (attempt 79 / port 19751) with exactly two changes:

- the launcher exports `MODEL_PATH=/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`
  (the base keeps the USB path only as its inert `${MODEL_PATH:-...}`
  default); the client's tokenizer path and the client/supervisor server
  command identity checks move with it;
- the bounded root-NVMe read guard rises from 134,217,728 to 536,870,912
  sectors (64 GiB to 256 GiB) in the launcher pre-check and the supervisor's
  per-second guard, because the load itself reads 173 GB from that disk. The
  corrected-AER guard (at most 64 events) is unchanged, so a return of the
  error storm still stops the run.

Everything else, including every pinned output hash of the frozen client, is
the A73/A78 packet. Packet: launcher `f5353bd7...`, client `c4fc2282...`,
supervisor `19d1fce8...`, host wrapper `8836b0ed...`.

## Reading

- Client passes with the same outputs as A73/A78 and `Loading weights took`
  well under 550 s: the lane can iterate from the NVMe copy; later packets
  inherit the path and the cap.
- Same outputs but no meaningful load-time gain: the loader, not the disk,
  bounds the load; keep the USB path (no reason to change a working
  identity).
- Any output difference: impossible for identical bytes; treat as a
  corrupted copy and re-verify before anything else.
- Guard stop (AER delta or PSI): the NVMe path is not yet safe for this
  lane; record the counters and stay on USB.
