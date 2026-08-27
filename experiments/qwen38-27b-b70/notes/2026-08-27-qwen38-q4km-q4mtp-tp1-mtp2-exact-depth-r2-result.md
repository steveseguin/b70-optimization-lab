# Qwen3.8 Q4_K_M + Q4_0 MTP2 TP1 exact-depth result

Status: **failed partial; 2K quarantined; 4K-32K Grade D exact cells**.

The one-B70, TP1, MTP2 server used the exact packaged target, draft, binary,
backend, F16 target/draft KV, graph-off, cache-off, reasoning-off identity. Six
frozen exact-token prompts requested 128 raw output token IDs at active depths
2K through 32K. Every transport, token-count, cache-zero, no-truncation, and
timing gate passed. Objective canaries passed and the server recorded 547
accepted of 648 drafted tokens (84.41%).

| Active context | Decode tok/s | TTFT | MTP0 token oracle | Disposition |
| ---: | ---: | ---: | --- | --- |
| 2,048 | 36.435975 | 2.082 s | diverged at generated token 23 | quarantined |
| 4,096 | 42.789429 | 4.136 s | exact | Grade D measured |
| 8,192 | 48.012864 | 8.450 s | exact | Grade D measured |
| 16,384 | 40.518008 | 17.837 s | exact | Grade D measured |
| 24,576 | 39.554909 | 28.201 s | exact | Grade D measured |
| 32,768 | 37.583325 | 39.439 s | exact | Grade D measured |

The first run stopped correctly at the 2K divergence. The second collected all
depths but its report composer failed after measurement by sorting the
`depth-*.stdout.json` files as receipts. A separately preregistered zero-GPU
recovery verified ten sealed raw artifacts and composed the structured result;
the original procedural failure remains preserved.

This is a synthetic repeated-token shape fixture, not representative natural
prose. No interpolation or extrapolation is permitted. The short-prompt strict
headline remains separately valid on its 12-prompt oracle, but this audit shows
that MTP2 is not universally target-exact across context/content shapes. The
2K point must never be published as a speed, and the five exact cells do not
constitute a whole-profile quality pass.

Evidence:

- `../data/2026-08-27-qwen38-q4km-q4mtp-tp1-mtp2-exact-depth-r2-result.json`
- `../data/2026-08-27-qwen38-q4km-q4mtp-tp1-mtp2-exact-depth-r1-prereg.json`
- `../data/2026-08-27-qwen38-q4km-q4mtp-tp1-mtp2-exact-depth-r2-amendment.json`
- `../data/2026-08-27-qwen38-q4km-q4mtp-tp1-mtp2-exact-depth-r2-report-recovery-prereg.json`
- `../data/qwen38-q4km-q4mtp-tp1-mtp2-exact-depth-20260827-r1/terminal-receipt.json`
- `../data/qwen38-q4km-q4mtp-tp1-mtp2-exact-depth-20260827-r2/terminal-receipt.json`
