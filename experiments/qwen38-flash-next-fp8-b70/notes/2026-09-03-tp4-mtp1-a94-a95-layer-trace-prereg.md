# A94 / A95 preregistration: layer-by-layer trace at the 2K divergence position

Date: 2026-09-03, about 14:15 EDT

## Why

After the recurrent kernel (A85), the dense GEMMs and the Triton MoE
(offline gates), the QSA index side path (A93) and graph replay (A83) are
cleared, the exact-recurrent MTP1 line still diverges from the MTP0 line
at token 12 of the 2K fixture (`29a2947a...` versus `afffd211...`), and
nothing measured so far says which layer computes something different in
a two-row verification step. The lane's repeatability trace records every
decoder layer's output (and the PLE, hyperconnection mix, attention and
MLP sub-records) for the first forward whose positions reach a gate; with
per-row digests (overlay `d132de8c`) a two-row capture can be compared row
by row against a single-row capture.

## Design

Both packets derive from the eager A83 packet (eager because the trace runs
in Python and a captured graph replays without it) at 4352 tokens from the
NVMe copy, with the trace armed on every rank at `MIN_POSITION=2059` (the
input position of token 12), one capture:

- A94 (`tools/rewrite-q38-a83-to-a94-layer-trace.py`, port 19766): MTP0,
  128 MiB KV, no speculative config.
- A95 (`tools/rewrite-q38-a83-to-a95-layer-trace.py`, port 19767): MTP1
  with `MTP_EXACT=1` on the sealed exact stage (the A85 identity, eager).

Each driver sends the exact-2K fixture request once and stops. The tokens
through position 2059 are identical on both lines (the first eleven
generated tokens match), so the two captures share their prefix.
`tools/compare-q38-layer-traces.py` picks the A95 row at position 2059 and
reports the first record whose digest differs from A94's.

## Reading

The first differing label names the component: `layer_N_attn_mix` or
`_mlp_mix` (hyperconnection), `_ple_output` (n-gram embedding), the
`layer_N_output` of a `full_attention` layer (QSA main kernel), of a
`linear_attention` layer (recurrent path after all), or `_mlp_output`
(MoE in situ, contradicting the offline gate). If every record matches
through the last layer, the difference is downstream of the model
(final norm, logits, or the sampler).
