# One-card FP8 package re-acceptance with the chunked-upload overlay (October 4, 2026, 16:33-17:32 UTC)

Receipts from
[`run-20260918-fp8-onecard-r312d-campaign.py`](../../scripts/run-20260918-fp8-onecard-r312d-campaign.py), the same
campaign as the [October 3 acceptance](../2026-10-03-fp8-onecard-noswap/), run again because the package now ships
[`overlays/b70_chunked_upload.py`](../../../../packages/qwen38-27b-fp8-tp1-b70/overlays/b70_chunked_upload.py). The
overlay sends every transfer over 256 MiB between host memory and the card in 128 MiB pieces while the model loads,
which avoids the driver path behind the model-load GPU fault
([what it is](../../notes/2026-10-04-gpu-fault-mtp-start.md)). The launcher (`serve.py`) is byte-unchanged; it copies
the whole `overlays/` directory, so the new file loads by itself. Host kernel 7.0.0-38-generic, same `r312d-c` image,
same references.

- Source run directory `/mnt/fast-ai/bench-results/fp8-onecard-chunked-20261004/`, unit
  `fp8-onecard-acceptance-20261004b`, repository at `ae7c15cb4`.
- Every comparison is against the same R311b no-MTP references as before
  ([`2026-09-17-fp8-ckpt2`](../2026-09-17-fp8-ckpt2/)) and the long corpus against probe-1's REF5
  ([`2026-09-17-fp8-probe1`](../2026-09-17-fp8-probe1/)).
- The two per-request ladder dumps are represented by their `*-ladder-vs-mtp0.json` verdicts, as before.

## Result

| Profile | Strict vs no MTP | Writing speed | October 3 | Anonymous memory | `oom_kill` |
| --- | --- | ---: | ---: | ---: | ---: |
| `recommended` | **12/12** twice | **54.047 / 54.026 tok/s** | 54.062 / 54.031 | 7.67 GiB | 0 |
| `max-context` | **12/12** | 54.023 tok/s | 53.978 | 7.00 GiB | 0 |
| `no-quantization` | **12/12** | 52.188 tok/s | 52.203 | 6.84 GiB | 0 |
| two-card package, started after the three | **12/12** vs the comm-2 no-MTP reference | 90.123 tok/s | 90.235 | | |

The other gates of each profile (ladders, context screens, the long corpus, chat quality and the logprob replay on
`recommended`) passed as on October 3; see [`results.json`](results.json) and [`campaign.log`](campaign.log).

**The overlay ran in every server.** Each one-card start logged
`b70_chunked_upload: 6 transfers over 256 MiB went between host and card in 128 MiB pieces (14.21 GiB)`, and the
two-card start logged four per card (4.74 GiB). Zero GPU fault lines in the kernel log for the whole campaign.

**No server was left running.** The campaign ends by starting the two-card package to check it; that server was
stopped gracefully at 17:32 UTC, as the owner's rule requires. `service-state.json` shows the stopped state.
