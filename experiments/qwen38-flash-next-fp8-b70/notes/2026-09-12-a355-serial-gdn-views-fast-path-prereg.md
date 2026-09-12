# Preregistration: A355 - narrow-view fast path for the serial GDN verifier rows

## Question

The block decomposition (A344-A350) put the second verify row's GDN at 11.2 ms against 2.4 ms for
one row (4.7x), while the MoE GEMMs went 11.3 -> 13.9 (1.23x). The serial verifier-row path
(`VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1`, the exactness selector that runs the decode kernel once per
row) surrounds each of its two kernel launches per layer with index_select + contiguous copies of
the inputs, index_copy of the outputs, and freshly allocated constant tensors - roughly 14
launches per layer per step on a card with one compute queue. Does removing that glue recover the
GDN excess while keeping the outputs bit-identical?

## Treatment

Overlay commit `bbda09ae` on the MTP1 diagnostic branch: `VLLM_XPU_GDN_SERIAL_SPEC_DECODE_VIEWS=1`
(off by default). For a single speculative request the packed rows are rows 0..R-1, so the
inputs are handed to the decode kernel as narrow views, the kernel writes straight into narrow
views of the outputs, and the constant query_start_loc / has_initial_state tensors are cached.
The kernel, its arguments' values, and the state copies between spec columns are unchanged, so
the arithmetic is unchanged. A355 = the A338 promoted MTP1 packet with step timing and the flag
printed into the derived server script (the derived launcher unsets inherited VLLM_* variables).

## Predictions

- Bit-identical: all three exact-2K rows hash `afffd211…`. Any other hash is a stop.
- Speed: M=2 forward well below 42.7 ms; if the glue was the whole excess, near 34 ms
  (27.2 + GDN's honest second row + MoE's +2.6 + QSA's share). Warm row rate above 37.4 tok/s.

## Stop rules

Hash mismatch on any row; server fails to become healthy (graph capture must accept the views).
