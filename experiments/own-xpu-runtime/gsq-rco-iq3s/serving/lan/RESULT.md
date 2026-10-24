# Commissioning result, 2026-10-24

`sc117-lan.service` was started once at 17:05:37 UTC (`run-20261024T170537Z`). It was ready at 17:07:12, about
95 s after start. No retries.

- **Startup self-tests.** Run 1 used fresh state. Run 2 came after a RESET, with the 320,459,412-byte dump released.
  Both runs reproduced the launch-b 32-token MTP output exactly, with the same 31 proposals: 26 accepted, 5 rejected.
- **Monitor.** Both rank processes were observed only on their own target cards: rank 0 on 23:00.0, rank 1 on
  47:00.0. The kernel-fault list was unchanged, there were no inconclusive samples, and the vision unit (PID 3487303)
  was untouched.
- **Retention.** After 8 requests the evidence run directory holds 12 MB: the rank base directories and the latest
  `req-000008`. Each release removed about 320 MB.

Client checks were run against `http://192.168.2.44:18160/v1`, the LAN address, from this host. The second LAN
machine (192.168.2.45) was offline, so no other computer has made a request yet.

| request | prompt | output | prompt wall | decode | MTP accepted | RESET |
|---|---:|---:|---:|---:|---:|---:|
| curl, code task (system+user, temperature ignored) | 47 | 109 (EOS) | 1.55 s | 26.0 tok/s | 106/109 | 4.18 s |
| curl stream, include_usage | 17 | 60 (length) | | | | |
| curl, thinking on (`reasoning_content` = "…17*23 = 391…", content "391") | 65 | 43 (EOS) | | 24.7 tok/s | 36/43 | |
| openai 2.45 SDK, normal and streaming | | | | | | |
| openai SDK, long critique | 1756 | 512 (length) | 63.5 s | 18.9 tok/s | 380/511 | 4.10 s |

Rates are service observations, not benchmark records. The engine processes the prompt one token at a time,
at about 28 tok/s. Each request after the first also pays about 4.1 s for the native RESET state dump to the USB disk.

Fidelity status is unchanged: the service is experimental and not quality-qualified (see [README](README.md)).

Biggest remaining costs:
1. Token-by-token prompt processing: 63 s for 1.7K tokens.
2. The 4.1 s RESET dump on every request.
3. 47 h lifetime per start.
4. Serial only.
5. No per-token streaming.
