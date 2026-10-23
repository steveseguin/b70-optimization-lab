# Boundaries

- Do not substitute packet193's two-card 840-byte-row kernel for this one-card 820-byte halfcache/indirect-slot kernel.
- Keep `p58ag_diet.hpp` byte-identical to the qualified micro; changing arithmetic requires new proof and device qualification.
- Keep cache capacity max23 in every view. Capacity gains cannot be reported as instruction-diet gains.
- Preserve layer 2's different-layout gate/up kernel. Exactly 47 sites switch.
- Do not interpret compute-window delta /48 as a direct kernel timer, or the micro projection as an engine result.
- No automatic rerun after a kill rule, client failure or device fault. Halt new device requests and preserve receipts. No reboot, driver reset, power changes or host-memory-setting changes.
- A 128-token screen is not strict512, fresh-process determinism, a final gate or a submission.
- Keep failed preparation receipts and negative device outcomes; never silently overwrite evidence.
