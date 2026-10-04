# Large host/card transfers now go in pieces (2026-10-04)

## In plain words

The GPU fault that has hit this host while models load is Intel's runtime losing a temporary mapping it makes for
any single transfer of 512 MiB or more between host memory and a card
([the full story](../../qwen38-27b-b70/notes/2026-10-04-gpu-fault-mtp-start.md)). The video lane made four such
transfers per clip plus one per session. They now go in 128 MiB pieces, which makes no mapping. The clips are
bit-identical to before.

## What was measured

- **The dividing line is exactly 512 MiB**, on this lane's own environment (torch 2.14, runtime 26.22): uploads of
  257 to 511 MiB make no mapping, 512 MiB makes one (`data/2026-10-04-piecewise-transfers/size-probe-h3-venv.txt`).
  The denoiser's largest tensors are 496 MiB, so they were never on that path.
- **Transfers that were on it:** the text encoder's 1,484 MiB embedding (once per session), and per clip the 741 MiB
  decoded video: card to host in the decode server, then host to card and back to host in the coordinator.
- **After the change** (`move_in_pieces` in `run_h3_t2v.py`, used at those five places): the runtime's allocation
  log shows no mapping of 512 MiB or more in the coordinator or the decode server.
- **Lossless:** two clips at the soak settings (544x960, 124 frames, 51 steps, seed 42, two-process decode) are
  bytewise equal to last night's soak clips: video, audio, both latents, and the `clip.mp4` files.

## Not done

- The two tile workers of the decode server each make about a hundred small host mappings per session (under
  1 MiB each). Same mechanism in principle, but every fault we have seen was at the large slot; left alone.
- The round trip of the decoded video through the card in the coordinator (host to card, then back) looks
  unnecessary. Removing it would save about 1.5 GB of transfers per clip; it is a behaviour change, so it gets its
  own gate.
