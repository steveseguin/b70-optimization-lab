# Qwen3.8 Flash-Next FP8 A19 NVMe-correlated reboot

Date: 2026-08-30
Status: infrastructure interruption; no model result

A19 passed all frozen preflights and launched at 11:10:34. The API and engine
processes initialized, but the last server line at 11:10:56 preceded worker
rank receipts and checkpoint shard progress. The kernel recorded a corrected
PCIe receive event for the local Samsung NVMe (`0000:01:00.0`) at 11:10:35,
the exact launch boundary. That is the final journal event in the boot; the
host then stopped responding and rebooted at 11:12:45.

This independently repeats A17's pre-shard host failure and follows an earlier
same-boot NVMe receive event during A18 warmup. There was no OOM kill, B70
reset/fault, client request, model output, trace, or timing. A19 is an
infrastructure interruption and changes no protected result. Attempt-19 paths
remain preserved and will not be reused.
