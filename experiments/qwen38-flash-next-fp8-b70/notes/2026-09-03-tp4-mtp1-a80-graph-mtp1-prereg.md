# Qwen3.8 Flash-Next FP8 A80 preregistration: MTP1 on the deterministic full-decode-graph line

Date: 2026-09-03
Status: frozen before launch; diagnostic arm gated on the MTP0 line's pinned
hashes (lossless or nothing)

## Question

The deterministic full-decode-graph MTP0 line is promoted at 4352 tokens
(A73/A78: short 22.66, exact-2K 13.99, exact-4K 12.78 tok/s). The native
eager line's MTP screens (MTP1-4 at 9.4-20.7 tok/s short) could never be
verified exactly because their servers were logit-jittery. Does the
publisher's MTP head, at one speculative token, run inside the full decode
graph on this line, and does it reproduce the MTP0 outputs bit for bit while
raising decode?

## Design

`tools/rewrite-q38-a79-to-a80-mtp1-graph.py` derives A80 from the frozen A79
packet (NVMe model copy, 256 GiB read cap) with three server changes:

- the derived base's MTP freeze moves from `MTP=0` to exactly `MTP=1`, and
  the launcher exports `MTP=1` (the base then passes
  `--speculative-config {"method":"mtp","num_speculative_tokens":1}` and
  asserts `use_qwen4_exp_mtp()`);
- `cudagraph_capture_sizes` becomes `[1, 2]` with `max_cudagraph_capture_size`
  2, so the two-row verification step is captured (the 27B FP8 lane's
  MTP1 gained nothing with size `[1]` alone);
- `KV_CACHE_MEMORY_BYTES` becomes `376569856`, the 32-block MTP1 headroom
  value the 2026-08-27 eager MTP1 4352 arm served exact 4K with.

The supervisor's identity checks follow (`mtp`, capture sizes, KV bytes);
the frozen client is renamed for hash pinning only. The arm is driven by
`a80-diag-driver.sh` (scratch, mirrors the client's invocations): three
short rows, two exact-2K rows, two exact-4K rows, the 7-case quality suite
with 16-repeat and exact-2K needle, and `/metrics` before and after for the
speculative-decode counters. Attempt 80 / port 19752. Packet: launcher
`234daed6...`, client `35fbfd75...`, supervisor `9f543468...`, host wrapper
`e05d865d...`.

## Reading

- Short hash `5f407446...`, 2K `afffd211...`, 4K `c6193cc6...`, repeat
  `3b0b3192...`, 6/7 semantic with the same normalized outputs: MTP1 is
  exact on this line. Its short and depth rates against the MTP0 record are
  the result; a frozen client with the MTP1 identity (and a receipt
  verifier that counts size-2 FULL dispatches) then makes it a record.
- Any hash difference: the MTP1 verification path is not bit-exact against
  MTP0 on XPU with the graph; record where it diverges (token index, logprob
  gap if probed) and try MTP1 eager on the deterministic line to separate
  graph from speculation.
- Server fails to start (graph capture with the draft, KV budget, schema
  asserts): the negative names the boundary; MTP on this line then needs
  code, not a packet.
