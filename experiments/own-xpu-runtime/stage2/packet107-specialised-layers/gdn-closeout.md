# Packet107 GDN closeout

Question: can shared per-head preparation remove repeated norm/gate work while
preserving the packet97 ordinary layer-4 arithmetic and BF16 recurrent state?
Identity: copied packet97 source, `iq3-p49-split32-v1`, 48 value/16 key heads,
128 dimensions, M=1, four consecutive tokens, GNU 13 and Intel 2026 compilers.

The finite GNU complete-layer gate passed. GNU's exceptional operator checks
also passed. Intel's s6 NaN-payload case failed at output byte 1572864 of the
combined state/output transcript: expected low byte 193 (`0x7fc1`), actual 192
(`0x7fc0`). The first 1,572,864 recurrent-state bytes matched. This is an exact
output failure, not a speed result. Restoring production's four-row host loop
and strict exception handling did not fix it; no payload canonicalisation or
production fallback is accepted. The arm is closed before device admission.

Useful retained mechanism: 32 independent head-normalization trees replace
3,072 repeated trees; the parallel recurrence and BF16 inter-token state remain.
This costs an extra kernel and FP32 preparation traffic, so there is no assumed
speedup. Failed source, case transcript, first byte differences and binary hash
are in `evidence/gdn-closed/`; final leaf receipts retain the failure explicitly.

Revisit only with a new arithmetic-preserving implementation that passes both
compilers' complete exceptional state/output gate, not a weaker fixture or an
output tolerance. QSA's independent shared-KV arm continues in this packet.
