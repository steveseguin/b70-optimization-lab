# Qwen3.8 Flash-Next FP8 A87 preregistration: serial verifier-row attention on the exact recurrent MTP1 line

Date: 2026-09-03
Status: frozen before launch; diagnostic gated on the MTP0 line's hashes

## Question

After A85 (exact recurrent spec-decode path) the MTP1 2K continuation
agrees with the MTP0 line through token 11 and flips at the token-12
near-tie; 4K is unchanged. The offline GEMM gate cleared the oneDNN dense
projections (M=2 equals two M=1 bit for bit on every decode shape) and the
MoE map already resolves M=2 to the M=1 config, so the two-row
FlashAttention path of the 12 full-attention layers is the prime suspect,
exactly the 27B FP8 lane's R38 finding. Does attending the verifier rows
one at a time through the single-row decode call make MTP1 reproduce the
MTP0 line?

## Design

Overlay commit `d3a61403` (on `2169dbfe`) ports R38 to this vLLM tree:
behind `VLLM_XPU_FA_SERIAL_SPEC_DECODE=1`, a multi-row query batch on XPU
is attended one row at a time through the same `flash_attn_varlen_func`
call the plain decode step uses (per-row `seqused_k`, the same `num_splits`
policy), off by default, no other path touched.
`tools/rewrite-q38-a85-to-a87-serial-spec-attn.py` derives A87 from the
frozen A85 packet: the two head literals move to `d3a61403`, the derived
server exports the flag next to the mkldnn flag, and the derived-source
assertions check both. Same driver battery and pins as A81/A85. Attempt
87 / port 19759.

## Reading

- All pinned hashes match (2K `afffd211...`, 4K `c6193cc6...`): MTP1 is
  lossless on this line; its rates against the MTP0 record and A85 are the
  result, and a frozen client with the MTP1-exact identity and a size-2
  receipt verifier turns it into a record pair.
- 2K divergence moves later still or 4K starts matching: attention was a
  part; whatever remains is in the MoE kernel at M=2 or the sampler.
- No change from A85: the attention path was not it; the remaining
  candidates are the Triton block-FP8 MoE at M=2 and the rejection sampler.
