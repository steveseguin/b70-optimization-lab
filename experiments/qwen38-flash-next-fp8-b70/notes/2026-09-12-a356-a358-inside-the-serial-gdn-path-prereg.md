# Preregistration: A356-A358 - inside the serial GDN verifier-row path

## Result that motivates this

A355 (`VLLM_XPU_GDN_SERIAL_SPEC_DECODE_VIEWS=1`, overlay `bbda09ae`) is bit-identical (three rows
`afffd211…`) but the M=2 step only moved 42.7 -> 41.8 ms. The index/copy glue around the per-row
kernel launches was worth 0.9 ms, not the 8.8 ms GDN excess. Under full-graph replay the launches
are cheap; the cost is in what the launches do.

## Arms (MTP1 promoted line, step timing, exact-2K rows; timing only, outputs will change)

- A356: serial path off (`VLLM_XPU_GDN_SERIAL_SPEC_DECODE=0`, the batched spec path this lane
  retired for tie-site exactness). Measures the price of the exactness selector at M=2.
- A357: serial path + views, `Q38_DIAG_SKIP=gdn_serial_kernel` (the per-row decode kernel not
  launched, row outputs zeroed). Measures the two kernel launches themselves.
- A358: serial path + views, `Q38_DIAG_SKIP=gdn_serial_state_copy` (no accepted-state copy into
  column 0, no column j-1 -> j copies). Measures the state copies.

Overlay head: the MTP1 diag branch with the skip switches (commit recorded in the A356 packet).

## Predictions and what each outcome means

- If A356 lands near 34 ms, the serial path costs ~8 ms at M=2 and the lever is a two-row exact
  kernel (one launch per layer, row 0 then row 1 with the state carried in registers) or an exact
  batched kernel - an extension rebuild.
- If A357 recovers most of the excess, the per-row decode kernel is slow at num_decodes=1 with the
  spec state layout (each launch reads and writes a full state slot): same lever.
- If A358 recovers most of it, the state copies are the cost (each is a full-slot index_select +
  index_copy on conv_state and ssm_state, twice per row): the lever is to make the kernel read
  column j-1 and write column j directly, no copies - a kernel argument change.
- If none moves it, the excess is outside the serial function (the conv update or projections at
  M=2) and the next arm skips those.

## Stop rules

Server fails health; timing rows fail. Hashes are expected to differ from `afffd211…` on A357/A358
and may differ on A356.
