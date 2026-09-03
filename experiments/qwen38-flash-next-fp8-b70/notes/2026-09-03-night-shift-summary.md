# Night-shift summary, 2026-09-02 23:00 to 2026-09-03 02:10 EDT (four-B70 host)

## Qwen3.8 Flash-Next FP8 TP4 (this lane)

- **Cause of the run-to-run logit jitter found and fixed.** The A65 in-server
  trace localized the first non-repeatable operation to a K=10240 BF16
  oneDNN GEMM in the layer-0 hyperconnection mix (rank 0), propagated by the
  TP all-reduce. `VLLM_XPU_MKLDNN_DETERMINISTIC=1` in every XPU worker
  (overlay 805cde59) made the eager line logit-exact at depths 8-2048 (A66)
  and the full-decode-graph line exact at every probed point (A67).
- **Three fresh servers of the deterministic graph identity agree on every
  output** (A70, A71, A72): 6/7 semantic with the inherited miss, 16/16
  repeat on the protected hash, exact 2K needle, one exact-2K output hash
  `afffd211...` on all six rows. Short rows 22.3-24.2 tok/s (three-attempt
  center `23.03` vs native A56 `23.63`); exact-2K rows 13.2-14.6 tok/s
  (above A56's 12.3-13.0).
- **Receipt defect fixed.** The frozen client's runtime verifier expects the
  `--cudagraph-metrics` dispatch table, which no Flash-Next server had ever
  printed: the XPU worker runs the V2 model runner, which never built
  `CUDAGraphStat` (Codex read-only audit). Overlay 2169dbfe adds it; A72
  then passed the entire frozen client, exit 0, with 1213 size-1 FULL
  dispatches receipted. A72 is the complete promotion record.
- **Open for the user:** the exact-2K authority. The deterministic line's
  `afffd211...` (three servers) versus the protected native-line
  `5fd297f7...` (one 2026-08-27 server of a class shown to be jittery);
  both are well-formed continuations diverging at a near-tie token. Decision
  memo: `2026-09-03-tp4-mtp0-exact-2k-authority-decision-memo.md`.
  Nothing protected was changed. A73 (exact-4K rows) is proposed and waits
  on that policy: `2026-09-03-tp4-mtp0-a73-exact-4k-proposal.md`.

## Qwen3.8 27B FP8 TP2 R139 recipe (replayed on this host)

- Complete and reproducible: fresh full clone, binary-route builds of R55C,
  R62 and R139, extension digest `f912e12d...` reproduced, model verified,
  strict-bench gates pass on both profiles. README now says to clone with
  full history (shallow clones fail the closure verifier's source-commit
  binding).
- Graph-off decode is host-bound here: MTP1 28.9 / MTP0 18.6 tok/s versus
  54.6 / 33.3 published. Cause: per-launch host submission cost (5.2 vs
  3.1 us per launch, 48 vs 13 us per two-card all-reduce). ECC (off),
  governor, CCD pinning, `iommu=pt`, ACS redirect and GuC firmware each
  changed nothing.
- XPU Graph recovers it: `FULL_DECODE_ONLY` with capture sizes `[1,2]` gives
  MTP1 **52.05** and MTP0 **31.53 tok/s** (95% of both headlines), outputs
  identical to graph-off MTP0 on all 12 strict prompts, and the 2K-32K
  real-content curve at 51.2 to 49.1 tok/s (MTP1, 18/18 exact against its
  MTP0 oracle) and 31.1 to 28.5 (MTP0). Graph wrappers are tracked in the
  package (`run-w8a16-{mtp1,mtp0}-strict-server-xpugraph.sh`) with a README
  section. The graph-on c1-c64 identity ladder run afterwards: MTP1 exact
  through c16 (c32 29/32, c64 59/64), MTP0 exact through c8 with one miss of
  sixteen at c16 (c32 31/32, c64 58/64); documented variants, not qualified. Note and data:
  `experiments/qwen38-27b-b70/notes/2026-09-02-qwen38-fp8-r139-four-b70-host-replay.md`.
- Publication closure: Laguna, MiniMax and Gemma recipe scripts are now
  portable (env overrides, fail-closed defaults, two lab-only inputs copied
  into their packages); 0 of 17 packages with gaps.

## Host state this morning

- Kernel line carries `iommu=pt`. ACS redirect was cleared on all eight
  B70 root and switch ports for this boot only (`setpci ECAP_ACS+6.w=0`;
  original `0x001d`); it reverts at the next reboot. GuC 70.72.1 loaded;
  card order 43->card0, 47->card2, 23->card3, 27->card4; CPU governor
  powersave (measured harmless). No GPU faults overnight.
