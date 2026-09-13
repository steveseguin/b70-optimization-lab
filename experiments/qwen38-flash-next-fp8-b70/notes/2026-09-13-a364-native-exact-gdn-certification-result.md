# A364: the extension's exact serial GDN mode passes the certified MTP1 client battery

Preregistration: `2026-09-12-a364-native-exact-gdn-certification-prereg.md`. Packet: the certified
A305 frozen-client packet with only the kernel stage (`runtime-gdn-roundstate-bbae3c5-b70`), the
exact-mode exports and the client's matching identity checks moved
(`tools/rewrite-q38-a305-to-a364-native-exact-gdn-certification.py`). Launched through
`tools/q38-a364-client-driver.sh` (waits for health, then runs the frozen client). Server healthy
at 01:13:54 UTC 2026-09-13, client battery complete at 01:17:55, clean stop.

Client verdict: `PASS recovery quality short-repeat exact-2K-repeat exact-4K-repeat PLE-only 4352
MTP1 QSA-stable treatment` (`data/20260913-tp4-mtp1-a364-native-exact-gdn-client-gates-passed.txt`).

| gate | A305 (certified line) | A364 (exact serial GDN mode) |
|---|---|---|
| quality screen | 6/7, sole known miss code_execution=30; 16/16 one hash; exact needle | identical |
| short rows p146/o256 (tok/s after TTFT, x3) | 42.89 / 43.03 / 43.04, median **43.03** | 53.38 / 53.41 / 53.41, median **53.41** (+24.1%) |
| short output sha256 | 5f407446… | 5f407446… |
| exact-2K (conventional 99-interval tok/s, x2) | 38.98 / 38.97 | **48.16 / 48.21** (+23.6%) |
| exact-2K output_token_ids_sha256 | afffd211… | afffd211… |
| exact-4K (x2) | 39.30 / 39.30 | **48.52 / 48.49** (+23.4%) |
| exact-4K output_token_ids_sha256 | 1d833e5f… | 1d833e5f… |
| recovery canary | passed | passed |
| identity | vllm 6d872457, kernels e421889, stage build 2f829747 | vllm 6d872457, kernels e421889, stage build **bbae3c5** |

Every pinned output is byte-identical to the certified line at 2K and 4K; the only change is the
kernel stage and the verifier-row selector. Evidence filed under
`data/20260913-tp4-mtp1-a364-native-exact-gdn-*`.

## Launch incidents (recorded, no effect on the result)

1. The first launch (12:48 UTC 2026-09-12) froze the host silently at startup, same class as the
   two 2026-09-03 freezes; reboot at 13:22 UTC.
2. After the reboot the evidence drive had to be remounted and the root NVMe had dropped under the
   launcher's 220 GB floor; unused models (laguna-s-2.1, muse-glimmer, the 9B pair, 100 GB) were
   moved to /mnt/raid-models with symlinks left in place.
3. The certified client checks the run directory and /health immediately, so it cannot be the
   launcher's driver; the health-waiting wrapper was added.
4. The client's official-resolver env and live-server PYTHONPATH check carry the stage path; the
   generator now moves them too.

## Next

A365: the same packet on a fresh server (the fresh-server-repeat gate), then the promotion
attestation and the record submission.

## Addendum (02:15 UTC): three servers, one identity

A365 (fresh server, same packet) and A366 (a third server; its packet was meant for the record
suite but carried the battery client) both returned the same verdict and pins: short medians
53.43 / 53.46, exact-2K 47.90-48.26, exact-4K 48.49-48.54 tok/s, `afffd211…` and `1d833e5f…` on
every row, quality 6/7 with the inherited miss, 16/16 repeat, canary passed. Evidence:
`data/20260913-tp4-mtp1-a365-*`, `data/20260913-tp4-mtp1-a366-*`, pair summary
`data/20260913-tp4-mtp1-native-exact-gdn-exact-2k-pair-summary.json`. The record number comes
from A367: the same packet's server under the record gate's suite driver
(`repro/qwen38-flash-next-fp8-tp4-mtp1-qsafused-b70-38tps-20260907/wait-and-run-client.sh`), the
fixed cold 12-prompt realistic suite sent once.
