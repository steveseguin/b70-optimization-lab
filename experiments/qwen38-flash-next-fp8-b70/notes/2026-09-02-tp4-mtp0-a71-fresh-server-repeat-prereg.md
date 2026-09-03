# Qwen3.8 Flash-Next FP8 A71 fresh-server repeat preregistration

Date: 2026-09-02
Status: frozen before launch; promotion evidence arm; runs after the 27B TP2
public-chain replay releases the GPUs

## Question

A70 (full decode graph, public oneCCL twoshots, tuned M1 W13-N32 map,
`VLLM_XPU_MKLDNN_DETERMINISTIC=1`) passed every protected quality gate and
produced one exact-2K output hash on both rows, `afffd2110812...`. Does an
independently started server of the same identity reproduce every gate and
that hash byte for byte, and what are its rows?

## Design

`tools/rewrite-q38-a67-to-a71-fresh-repeat.py` derives A71 from frozen A67
exactly as A70 was derived (64 GiB bounded-read cap, restored helper pin,
verifier hash `94487432...`, head receipts `805cde59...`,
`mkldnn_deterministic=1` receipt) with fresh attempt paths (attempt 71 /
port 19743, new compile and runtime caches) and one further change: the
client's exact-2K pin is the deterministic candidate `afffd2110812...`
instead of the 2026-08-27 native-line record `5fd297f7...`. No protected
file, hash, or result is modified; the pin lives only in this attempt's
frozen client. Packet: launcher `a8c9385d...`, client `f7e3cffe...`,
supervisor `895b03b7...`, host wrapper `6d1ba21c...`.

## Reading

- All gates pass including the candidate 2K pin: two fresh servers agree on
  every output; the deterministic graph line is promotable, with its short
  median reported as the two-attempt center against A56's `23.626811 tok/s`
  and the authority question (native `5fd297f7...` versus deterministic
  `afffd211...`) put to the user with both records intact.
- The 2K pin fails with a third hash: the deterministic flag does not close
  cross-server exactness at 2K; the trace is re-armed at that depth.
- Any other gate fails: recorded; no promotion.
