# Preregistration: Qwen3.5-9B broad determinism/speed campaign (2026-09-09)

Open-ended optimization campaign requested by the operator: raise decode tok/s on Qwen3.5-9B while
holding determinism, losslessness and error-free operation across MTP depths 0-3, concurrent
sessions, and context from ~2K to ~32K. Runs until the operator stops it.

## Host

`steve-b70s`: **four** Intel Arc Pro B70 32 GiB (xpu-smi IDs 0-3 = BDF 23/27/43/47:00.0 =
card3/card4/card0/card2), 125.7 GiB RAM, root NVMe AER counters clean this boot. `CURRENT.md`'s
"two B70s / steve-TURIND8-2L2T" header describes a different machine and is stale here.

## Route decision (operator, 2026-09-09)

W4A16 primary, FP8-dynamic as control; TP1 only; parallel arms across the four cards.

The 2026-09-07 pair already settled which route can carry this spec. `int4_gemm_w4a16` is
row-count invariant; the FP8 GEMM is not. A verify step at MTP depth `d` processes `d+1` rows, so
depth and concurrent-user count are the same knob, and one kernel property governs both of the
operator's hardest requirements:

| | W4A16 | FP8-dynamic |
| --- | ---: | ---: |
| MTP3 headline | 113.627 / 112.904 tok/s | 98.251 / 98.027 |
| Lossless MTP 0-3 | yes | yes |
| Lossless MTP 4/5/6 | yes (12/12) | no (8/12) |
| Exact vs single request at 64 users | 64/64 both passes | 59/64 |

Known ceiling on the primary route: the RMSNorm is *not* row-count invariant and gives ~2-3% of
rows a last-bit difference once the batch reaches 16. It only changes a token when it lands on a
near-tie (1 request in 448 across the 96/128-user rungs). TP2+ carries a separate unresolved
nondeterminism (25 divergences over 12 fixed tie sites, ~0.7% of requests) and is out of scope.

## Identity

- Model: `RedHatAI/Qwen3.5-9B-quantized.w4a16` @ `a398088c4228b0ae0c8c78df88fd1e4bf445f068` (11.46 GB),
  control `RedHatAI/Qwen3.5-9B-FP8-dynamic` @ `790f0576d2d77dd5322aa0603a470bd9e3a3d1f6` (14.03 GB).
  Both were absent from this host at campaign start and were re-fetched at the pinned revisions.
- Runtime: R276, `sha256:521eb277c0733f8c2ce47aea1bb98ed576c6f1ad63bf5baf22d38fc07abf54ad`,
  re-pulled from ghcr and verified equal to the pinned digest before any launch.
- Harness: `scripts/run-20260909-qwen35-campaign-v3.sh`. v2 is preserved unchanged; v3 exists
  because three v2 literals abort on this host (absolute repo path; a `Device State: normal`
  gate this xpu-smi build never prints, required to equal 2; host-wide container and all-card
  health checks that make parallel single-card arms abort each other).

## Phases

> **Correction (same day):** the published `w1` pair was measured on a two-card, 15.5 GiB host, not
> on `steve-b70s` (125.7 GiB, four B70s). P0 is therefore this host's own baseline, not a
> cross-host reproduction, and levers are ranked against it. See the
> [P0 note](2026-09-09-p0-reproduction-and-a-lying-pcie-register.md).

**P0 - reproduction gate (serial, card 0).** Re-run the published w1 configuration on the
re-fetched checkpoint: strict MTP0 pair + MTP3 pair, G1/G2/G3. Passes only if G1/G2/G3 are 12/12
and the MTP3 class-balanced median lands within the host's known 3% back-to-back drift of
`113.627 / 112.904`. Nothing downstream is trusted until this passes: it is the only check that
the re-download and re-pull restored the measured identity.

**P1 - breadth (parallel, cards 1-3; no timing claims).** Losslessness and determinism across the
operator's matrix. MTP depth arms 0/1/2/3; concurrency ladders 1,2,4,8,16,32,64 with
`--require-output-identity`; real-content depth ladder 2K-32K with an MTP0 oracle arm. Speed is
recorded, never a gate, in this phase.

**P2 - optimization ladder (timed rows serial on card 0, host otherwise quiet).** Every lever is
gated on losslessness first, then timed as a two-fresh-server pair:
1. `GDN_SPEC_GROUP` (default 16) swept 8/16/32.
2. `cudagraph_capture_sizes` matched to the decode shapes the target really runs (`M = depth+1`
   per sequence times concurrency), rather than the inherited 1-64 list.
3. KV/context budget at 32K, respecting the headroom rule: never park a card within ~0.3 GiB of
   capacity or it pays whole-buffer PCIe migrations per cold touch.
4. `MAX_NUM_BATCHED_TOKENS` / chunked-prefill split for TTFT against decode.
5. MTP depth re-swept per context depth: depth 3 was chosen at short context and never re-tested
   deep, and the W4A16 route is lossless to depth 6.

## Rules

- Speed verdicts need two fresh servers; back-to-back control drift on this host is ~3% and up to
  10% across a session. Timed rows never run while another arm holds a card.
- An arm that fails its identity gate is recorded as a bounded negative and closed, not retried
  into a pass.
- Aggregate concurrent throughput is scoped capacity evidence. It never becomes a single-user
  headline and never goes in a LocalMaxxing `tokSOut`.
- No `xpu-smi` polling while a server is initialising.
- Kill only by pid captured at launch; never `pgrep -f`/`pkill -f` a pattern that appears in the
  calling shell's own command line.
