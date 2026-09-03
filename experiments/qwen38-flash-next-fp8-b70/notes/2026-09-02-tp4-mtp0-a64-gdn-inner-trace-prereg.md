# Qwen3.8 Flash-Next FP8 A64 in-server GDN inner-trace preregistration

Date: 2026-09-02
Status: diagnostic; frozen before launch; no promotion claim possible

## Question

A63 showed the same first-step jitter at the old overlay head, and the
fixed-input gates (`tools/run-q38-gdn-repeat-gate-a1.sh`, result
`gdn-repeat-gate-20260902-a1`) showed the staged `_xpu_C.gdn_attention`
operator bit-repeatable at the 8-token prefill, 64-token chunk with state,
32 chained chunks, single decode and 128 chained decodes, and the XCCL
BF16 all-reduce bit-repeatable at 1, 8 and 64 rows, each in-process (50 or
200 repeats) and across two fresh processes. The 2026-08-30 A24/A25 pair
put the first fresh-start difference at the layer-1 GatedDeltaNet output
with the hyperconnection mix feeding it exact. Which operation between that
mix and the layer output first differs between identical 8-token prefills
on one healthy server: the FP8 input projection, the GDN core kernel under
real inputs and real concurrency, the gated RMSNorm, or the output
projection with its TP all-reduce?

## Design

Overlay commit `69f905f1fb062cce782bbcb4850f3856924dc24b` (on top of
`cbc3cb58...`) extends the report-only repeatability trace with an exact
position window, a capture count, and GDN-internal records for selected
layers: `layer_N_gdn_in_proj` (hidden, qkvz, ba), `layer_N_gdn_core`
(core_attn_out, z), `layer_N_gdn_norm`, `layer_N_gdn_out_proj`, and
`layer_N_gdn_attn_output`. With no trace file set the production path is
unchanged; 16 trace tests pass.

`tools/rewrite-q38-a62-to-a64-gdn-trace.py` derives A64 from frozen A62 by
moving the head override to `69f905f1...` and replacing the two trace
`unset` lines with exports: trace file per rank under the attempt-64 run
directory, rank `all`, exact positions `0:7`, count 3, GDN layers `0,1,2`.
Everything else is A62: eager, bundled oneCCL, tuned M1 W13-N32 map,
external checkpoint, PLE-only UVA placement, 2304 max model length, host
guards. Attempt 64 / port 19736; names carry `gdntrace`. Packet: launcher
`f19f0fbe...`, client `b37bb78b...` (hash pin only), supervisor
`ec43ee9f...`, host wrapper `cde506cf...`.

The logprob probe runs with `--depths 8` only: its first three 8-token
prefills (positions 0-7) are captured on every rank into
`gdn-trace-rank{r}.{0,1,2}.json`; the remaining requests run untraced.

## Reading

Compare the three captures per rank record by record in label order and
report the first differing label. Expected discriminations:

- `layer_0_gdn_in_proj.qkvz` differs while `hidden_states` matches: the
  FP8 input projection (activation quantization or GEMM) is the source.
- `gdn_core` differs with identical `qkvz`/`ba`: the GDN kernel is
  non-repeatable under real inputs or real concurrency even though the
  fixed-input gate passed; a state-slot or stream interaction is implied.
- `gdn_norm` differs with identical core output: the gated RMSNorm.
- `gdn_out_proj` differs with identical norm output: the output projection
  or the TP all-reduce under real inputs; per-rank files separate the two.
- All GDN records match on layers 0-2 while a later layer output differs:
  the source is outside GDN; the trace's layer outputs bound it to a layer.
- Captures are identical throughout while the probe's first-step logits
  still differ: the difference enters after the traced prefill forward
  (final norm, LM head, sampler logprob path).

No speed is claimed. Protected results remain unchanged. After the arm the
overlay stays at `69f905f1...` (a superset of `cbc3cb58...`) unless a
follow-up requires otherwise.
