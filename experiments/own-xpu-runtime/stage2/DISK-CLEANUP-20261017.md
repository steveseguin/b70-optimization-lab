# Disk cleanup, 2026-10-17 about 04:20 UTC

Packet 49's K2 window refused at storage admission. Root had 21.37 GB free; the packet keeps an 8 GB floor plus a full-chain reserve, which capped the build budget at 3.85 GB. K2 needs 2.5 GB on top of 1.96 GB already used.

Following the 2026-10-12 cleanup rules (ignored, regenerable build output in finished packets only; nothing tracked; no receipts), the coordinator removed:

- `packet45-merged3/build/asan/` (1.35 GB): the sanitizer build. Packet 45 is closed at the 39.422 record, and its receipts are tracked under `data/own-xpu-runtime-packet45-device-rounds-20261014/`.
- `packet44-context/build/asan/` (0.72 GB): the sanitizer build of the closed packet 44.

No packet-49 seal or source references either directory, checked with grep. Window result trees, sealed reference tables and the only copies of untracked trees were not touched.
