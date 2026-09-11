# One server for every batch size: a draft-depth schedule, and what it took to make it real (2026-09-10)

The operating map said speculation is worth ~72% at one user and costs a third of aggregate
throughput at 64, and that no static depth is right for both. vLLM in R276 carries
`num_speculative_tokens_per_batch_size` (inclusive `[start, end, K]` ranges; the scheduler picks K
from the live batch size each step, the MTP proposer returns early at K=0). Schedule under test
throughout: `[[1,8,3],[9,16,1],[17,64,0]]`, the map's own crossover. Every arm below is its own
strict pair plus c1-c64 ladders with `--require-output-identity`, two passes per rung.

## Four attempts, one lossless

| arm | runner / graphs | one user | c8 | c16 | c32 | c64 | c32 / c64 exact |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| static d3 (reference) | v1, FULL_DECODE_ONLY | 110.7 | ~596 | ~667 | ~878 | ~909 | 32/32, 62/64 |
| static mtp0 (reference) | v1, FULL_DECODE_ONLY | 64.2 | 432 | 725 | 1148 | 1206 | 32/32, 64/64 or 63/64 |
| dyn1 | v1 - **ran eager** | 77.6 | 524 | 668 / 774 | 1044 / 1073 | 914 / 950 | 31-32/32, 63-64/64 |
| v2s3 / v2dyn1 | v2 runner | 82.2 / crashed | - | - | - | - | - |
| pw3 (static) | v1, PIECEWISE default splitting ops | 108.6 | - | - | - | - | - |
| pwdyn1 | v1, PIECEWISE | 108.5 | 598 | 766 / 876 | 1066 / 1081 | 995 / 955 | 31/32, 64/64 |
| pwdynm1, pwdynm1r | + Mamba active-allocation overlay | 108.6, 108.7 | 598 | 766 / 877 | 1066 / 1084 | 1145 / 1146 | 32/32, 64/64 |
| pwdynz (K=0 everywhere) | as pwdynm1 | 59 | 405 | 678 / 682 | 1090 / 1089 | 1150 / 1147 | 32/32, 64/64 |
| **fgdynm1** | **+ full decode graphs per K** | **110.67 / 110.73** | **623** | 766 / 852 | **1092 / 1090** | 1064 / **1150** | 32/32 + 31/32, 64/64 + 64/64 |

Strict gates G1/G2/G3 are 12/12 on every arm. Schedule everywhere: `[[1,8,3],[9,16,1],[17,64,0]]`.

- **dyn1**: `VllmConfig._maybe_override_dynamic_sd_cudagraph_mode` rewrites FULL_DECODE_ONLY to
  PIECEWISE under a schedule; this lane's `splitting_ops: []` then makes vLLM set cudagraph_mode
  NONE. The whole server ran eager. Still lossless, and already the schedule's exactness shape.
- **v2 runner** (`VLLM_USE_V2_MODEL_RUNNER=1`, which the override exempts): boots, captures, is
  lossless, but its speculative path is 26% slower at one user (82.2; mtp0 64.33), and with the
  schedule its speculator capture asserts on the K=0 range (`InputBatch.make_dummy`). Closed.
- **PIECEWISE with the default splitting ops** (attention and the GDN core ops eager per layer,
  the rest captured) costs 1.9% at one user and vLLM leaves it alone under a schedule. It beat
  static speculation at every rung from 16 up, and the Mamba active-allocation overlay
  (`docker/r276-dynamic-mamba-alloc.Dockerfile`, the 27B lane's August patch, applies to R276
  without fuzz) took c64 from 955-995 to 1145. **But it is not lossless**: on the 2K-32K ladder
  `structured-docs-4096` diverged from its own same-configuration mtp0 oracle at token 72, a
  near-tie site where three configurations each pick a different token (full-graph oracle 42707,
  piecewise oracle 4494, piecewise+schedule 84107). Piecewise changes the arithmetic on the eager
  path, and the 1-row oracle and the 4-row verify then disagree there. 17/18 is a fail.
- **pwdynz** sizes the residual against plain mtp0: with speculation configured and K=0 at every
  batch size the server is 5-6% under mtp0 at every rung. That is `propose()` running the draft
  layer forward before its K=0 early return - deliberately, so the draft KV/GDN state stays warm
  for when K rises. Structural, and not to be "fixed" by skipping it.
- **fgdynm1** keeps the published FULL_DECODE_ONLY numerics and captures one full decode graph per
  query length the schedule can produce (`docker/r276-dynsd-fullgraph.Dockerfile`, ~100 lines in
  `config/vllm.py`, `cudagraph_dispatcher.py`, `gpu_model_runner.py`; keys differ in num_reqs so a
  graph for 8x4 tokens is never replayed for 16x2; static configurations unchanged by
  construction). The ladder server captured 33 decode graphs (3 lengths x 11 sizes) against 11.
  One user comes back at the published 110.7 exactly; c8 gains 4% over piecewise.

## What is solid

`fgdynm1x`, the 2K-32K real-content ladder on the fgdynm1 server: **18/18 exact against its own
mtp0 oracle**, every decode figure equal to the static x32kr run (111.4 / 139.2 / 113.9 / 147.8 /
129.1 / 86.7 at 2K...32K). So one server now gives, lossless at every rung and context measured:
the published 110.7 tok/s at one user, 623 at 8, better-than-any-static at 16, 1090 at 32 and 1150
at 64 users - against mtp0's 1148 / 1208 - with the mtp0-level exactness at 32 and 64 that static
speculation loses. No operator choice, no restart.


## 2026-09-11: the draft-state catch-up recovers most of the residual

The preregistered overlay (`docker/r276-dynsd-catchup`, on top of `dynsd-fullgraph`): a pure-decode
step that schedules no drafts skips the draft layer's forward; the skipped positions' target hidden
states and next tokens live in a 256-position per-request ring and are replayed through the draft
layer as a prefill-shaped pass, in chunks of at most `max_num_batched_tokens`, the next time the
request is asked for drafts. The MTP draft layer is a full-attention layer with its own KV cache,
so the replay is exactly a prefill of that one layer over the gap.

Three iterations, each a measurement:

| arm | what changed | one user | c32 | c64 | verdict |
| --- | --- | ---: | ---: | ---: | --- |
| cudynm1 v1 | first version | 110.71 / 110.64 | crash | crash | first real catch-up was 1638 tokens > the drafter's 512-token buffers; chunking added |
| cudynm1 v2 | chunked | 110.66 / 110.58 | 854 / 1022 | 1118 / 1120 | **slower** than without: two host->device tensor creations per skipped step block on the whole GPU queue and cost the CPU/GPU overlap |
| **cudynm1 v3** | device-only skip path | **110.69 / 110.60** | **917 / 1113** | **1183 / 1184** | +3% at 64 users, +2% at 32; gap to no-speculation 4.6% -> 1.9% |
| cudynm1r | repeat of v3 | 110.65 / 110.60 | 916 / 1109 | 1182 / 1183 | reproduces |

All strict gates 12/12 in every run; c32 exact 32/32 in all four passes of the two v3 runs (the
identity claim by the two-run rule improves from 16 to **32 users**); c64 63/64 + 64/64 and 64/64 +
64/64; the 2K-32K ladder on the v3 server is 18/18 exact with the same decode figures as the static
run. The preregistered gate asked for 1.5% of the no-speculation server at 32-64; v3 lands at
1.9-3%, so the residual is not closed, but the mechanism is proven and the configuration is
strictly better than the one without it. What remains is the draft forward on the mixed prefill
steps while a rung fills (kept so every prompt's draft KV is written) and one catch-up per request
per threshold crossing.

Promoted 2026-09-11 as the guide's scheduled-server configuration (launcher default image
`qwen38-int4-r276-dynsd-catchup`, six overlaid files pinned by content).

## What is not, and what is next

- The 5% under mtp0 at 32-64 users is the draft-layer forward on zero-draft steps (pwdynz). Only
  a cheaper draft forward moves it.
- `fgdynm1r` (same boot) reproduces it: 110.61 / 110.54 at one user, c8 623 / 624, c32 953 / 1091,
  c64 1149 / 1149, gates 12/12. The cold first pass reads low (1064 at c64 in `fgdynm1`, 953 at c32
  here) and the warm pass sits at 1090-1150. `fgdynt` (four passes at 16 / 32 / 64 only) settles
  it: the low pass is the first pass the server runs at all - 459 at c16 when c16 comes first -
  and every later pass is steady (884 / 884 / 892; 1075 / 1092 / 1090 / 1091; 1151 / 1151 / 1150 /
  1151). Server warm-up, not a schedule-transition effect; the steady c32 / c64 figures are 1090 /
  1151. Exactness at those rungs is in
  the same intermittent band as plain mtp0 (31-32/32, 62-64/64).
- Attribution closed by `pw3x` (static depth 3, PIECEWISE, base R276, no schedule, no overlay):
  the same case diverges at the same token with the same tokens (oracle 4494, verify 84107). The
  piecewise identity miss is the graph mode alone, so PIECEWISE is dead for this lane in general,
  not just under the schedule. (`pwdyn1x` and `pwdynm1xr` were already queued and are redundant.)
- `fgdync128` (max-num-seqs 128, 64 and 128 users): scheduled 1151 / 1197 warm (64/64, 127/128) against
  the no-speculation server's 1203 / 1254 (64/64, 127/128). The schedule's last range carries K=0
  forward, and the ~5% bookkeeping cost carries with it.
- Not yet a promoted result: one boot. A fresh-boot confirm pair is the promotion gate, then the
  overlay becomes the lane's published operating configuration.
