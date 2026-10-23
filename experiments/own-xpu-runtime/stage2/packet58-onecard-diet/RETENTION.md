# Packet58-onecard-diet retention

Nothing bulky exists: the packet stopped before any build. Keep everything below in Git (about 60 KB in total).

| Path | What | Keep |
| --- | --- | --- |
| `README.md`, `DO-NOT-REPEAT.md`, `RETENTION.md` | the STOP finding, the carried rows, this file | yes |
| `stride_proof.py` | the pin-and-transcribe proof (11 source files by sha256, 27 verbatim lines, the two layout formulas) | yes |
| `evidence/layout-mismatch.json` | its receipt (820 vs 840 B, 2- vs 4-byte halves, 20 vs 19 bindings, indirect vs direct) | yes |
| `evidence/compiler-proof.json` | the two syntax-only `g++` static_assert receipts with the sources and the pre-compile host poll | yes |
| `evidence/units-poll.json` | the first unit/compiler poll (the `pgrep -f icpx` self-match is explained in the README) | yes |
| `evidence/dnr-grep.txt` | the DO-NOT-REPEAT grep over 258 files | yes |
| `build/onecard_stride.cpp`, `build/twocard_stride.cpp` | the two 200-byte proof sources (also embedded in the compiler receipt) | yes (tiny) |

No binaries, no device streams, no proposal, no `READY-FOR-DEVICE.json`. Parent trees (packet58-onecard-cache23,
packet58-onecard-cache23-chain, packet193-expert-diet, packet194-expert-diet-engine, packet58j-onecard-port) were read in
place and are pinned by digest in `evidence/layout-mismatch.json`; nothing was copied from them.
