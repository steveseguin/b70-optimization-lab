# Packet 118b at 121 frames, decoder graph off (2026-10-10 01:38–01:56 UTC): 1.04 s of work per second of video, byte-identical to 117

Boot 4aafe57b (owner accepted continued launches on this boot at 01:15 UTC; receipt
`data/resume-20261008/fault-archive-20261010T011831Z-owner-accept-receipt.json`). Health receipt
`postflight-pre118b-20261010T0134Z.json`. One controlled swap from the live 117 server (stopped 01:33:24 UTC after 63
chunks), five-minute gap, `--check-only` passed (after the `bin/python3` → `bin/python` launcher fix, commit 207df4d81),
launched 01:38:30 UTC: run `encoder-server-continuation-stream-118b-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f121`,
client `start-client-118b.sh 121 0 cone 1 1 fingerprint none` (work dir `/home/steve/ltx-stream/s118b-live01`), sink,
relay and LAN preview attached; this was the public stream. Controlled stop 01:56:10 UTC after 101 chunks; no fault line.

## Qualification

Verdict 6824dd4a6fae at 01:46:57 UTC: `passed`, exact replay c0/c1/c2 identical on every tensor, 4 signatures per
route; every dual snapshot (fingerprint beside the walk, all six labels on anchored chunks) agreed; no latch written.

## Output identity across packets (the strongest check available)

The 117 live run (01:20–01:33 UTC, same scenes, same base seed, chain from seq 0) and this run share 63 chunks:
`images_sha256`, `last_frame_sha256`, `anchor_sha256`, `preview_sha256` **identical on 63/63**. `cone_equal` true on
101/101 chunks. 118b changes no output byte, as designed.

## Cadence (medians, chunks 10–99; 117 live run tonight, chunks 10–62, in brackets)

| item | 118b, 121 f, dg0, fingerprint | 117 tonight | 117 certified (10-09) |
|---|---|---|---|
| period, submit to submit | **5.227 s** (4.97–6.38) per 5.04 s of video | 5.303 s | 5.40 s |
| work per second of video | **1.037 s/s** | 1.052 | 1.08 |
| `submit_to_sampler_start` (split total) | 0.501 | 0.51–0.52 | 0.52 |
| cone anchor decode on the chain (eager) | 0.915 | | 0.955 |
| display decode off-chain (eager) | 2.655 | | 2.68 |
| six snapshots per chunk | 0.358 s total, 0.059 s each; dual on 4/90 chunks (every 20th), all agreed; min margin 1.45 GB | | |

### Where the 0.50 s before sampler A goes (`timing_s.submit_split`, medians)

| bucket | s | what it is |
|---|---|---|
| `condition_a_tail` | 0.223 | the guarded stage A: before snapshot 0.058 + consume precomputed encode 0.055 + after snapshot 0.058 + ≈0.05 glue |
| `first_node_to_condition_a` | 0.121 | text window / reuse, anchor read |
| `request_before_snapshot` | 0.082 | the request's four-card snapshot |
| `before_request_checks` | 0.035 | |
| everything else | ≈0.04 | queue, executor, dispatch |

Reading: the fingerprint saved little because a snapshot's cost is not the walk but the four-card synchronize plus
memory reads (0.059 s per snapshot in fingerprint mode, against the 0.05–0.09 estimate for the walk). Three snapshots
sit on the chain before sampler A (0.20 s) and three more off it. The anchor read + text window (0.12 s) and the stage-A
consume (0.055 s) are the other on-chain pieces. Below 1.0 s/s needs −0.19 s more.

## Next (preregistered)

1. 118b launch 2: 121 frames, dg1, pool cap 1.0 (bounded decoder-graph pool against the 9.66 GB xpu:3 floor). The cone
   decode on the chain was 0.69 s under the graph shadow at 97 frames vs 0.915 eager here: a −0.2 to −0.3 s candidate.
   Launched 02:01 UTC after this run's controlled stop (names archived `output/archive-stream118b-f121-dg0-live-20261010T0156Z`).
2. Then the snapshot schedule (owner-level safety question: three on-chain four-card syncs per chunk = 0.20 s), and
   prep-ahead of the anchor read / text window (0.12 s).
