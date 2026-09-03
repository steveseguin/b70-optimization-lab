# R181: async-off control on the probe image; layer-0 GDN prefill is identical in the phantom and clean runs

Date: 2026-09-03 18:18-18:25 EDT, boot 88f0984f (clean). R176 probe image, `--no-async-scheduling`. Prereg
`data/2026-09-03-qwen38-fp8-r156-mtp2-phantom-state-slot-async-off-r181-prereg.json`. Results:
`/mnt/fast-ai/bench-results/qwen38-fp8-r156-mtp2-phantom-state-slot-async-off-20260903-r181/query-mtp1/`.

## Pass result

64/64 vs the MTP0 oracle, no phantom (R169 control reproduced on the probe image).

## Layer-0 comparison, R176 (async on, phantom) vs R181 (async off, clean), 64 prefills, both TP ranks

Script: scratch `compare-r176-r181.py` (parses `R176 gdn_pre` / `gdn_post` for `n_prefills=1`).

- Inputs to the layer-0 GDN kernel are the same for every request: token count, state page (1/10 alternation),
  `has_initial_state=[False]`, and for request 33 the `gdn_build` metadata is identical to the character
  (`query_start_loc=[0,31]`, state index 1, `block_table_row0=[[1,2,3]]`).
- `out_rows_abs` (the last four output rows of the layer-0 GDN core) are **equal to the printed float on all 64
  prefills on both ranks**, request 33 included.
- The written conv/ssm state is equal on 63 of 64 prefills; on request 34 the conv abs-sum differs
  (44210.9 vs 43621.7, ssm equal) with different stale input pages, which is the untouched fifth conv-state column
  (width 5, four written), not an output difference.
- R181 has a 65th prefill at the end (post-pass canary); alignment of the 64 pass requests is exact.

## Reading

The phantom is not produced at or before layer 0 of the prefill forward: embeddings, the layer-0 GDN kernel and
its metadata are history-independent. Combined with R180 (all GDN pages zeroed, phantom unchanged) and the
upstream attention-page zeroing, the remaining candidates are downstream of layer 0 inside the same prefill
forward (R170): the full-attention layers' prefill path (their metadata, slot mapping and the serial-FA verifier
path were never logged for this request), later GDN groups (pages 4 and 7, but R180 zeroed those too), or the
final-norm/logits row (R171 found the last hidden row wrong). The next probe logs, for prefill batches of <= 4
sequences, the last hidden row's abs-sum after every decoder layer plus the attention metadata (seq_lens,
query_start_loc, slot_mapping tail, block table) of each full-attention layer; one async-on server localises the
first diverging layer against the R181-style control.
