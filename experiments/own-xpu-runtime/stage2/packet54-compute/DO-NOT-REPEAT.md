# Packet54 bounded decisions

- Launch-gap work is closed by packet34's19.823 ms wall vs19.520 ms GPU sum.
- Dense QKV/attention are already near their measured bandwidth limit.
- Packet46's four-workgroup norm fusion slowed19.272 to35.6765 µs; retain
  the two-stage partial buffer and enough output groups.
- Single-workgroup route fusion would concentrate262144 comparisons; this
  round instead changes stage1 distribution and stage2 exact value reuse.
- Recurrence state is already register-resident; new candidates must share
  redundant head math, not merely rename that existing property.
- HC inject stays unchanged: only16 SG32 jobs per side and80 dependent
  additions per lane; changing the split count changes the oracle tree.
- Packet53b V16 gate/up and HC virtualization remain closed. Bank only its
  exact V8 gate/up, V16 down and V4 small-FFN winners.

- FFN `combine-vector4` is closed: finite full-shape bytes passed but actual
  compiled-production NaN output was `0x7fc0`, candidate `0x7fc1`. A copied
  scalar/noinline exceptional fallback did not repair it. Preserve
  `evidence-cpu/full-diagnostic-2/receipt.json`; do not canonicalize or discard
  payload bits to pass. Revisit only with a proven unchanged production fallback
  whose overhead can justify the 11.2 µs total class budget.

- Both norm variants are closed before device qualification: the exceptional
  fixture differs at output byte4098 (production `0x7fc1`, candidate `0x7fc5`).
  Calling a copied specialised scalar body on nonfinite partials did not
  preserve the actual compiled kernel's NaN operand selection. See
  `evidence-cpu/full-diagnostic-3/receipt.json`. Keep production normalization;
  `mix-vector4` tests mixing alone. Revisit only with an exact production-path
  solution, never a payload tolerance.

Device conclusions are pending. Add an evidence-linked closeout after the
coordinator's complete result; do not edit sealed code to chase a speed.
