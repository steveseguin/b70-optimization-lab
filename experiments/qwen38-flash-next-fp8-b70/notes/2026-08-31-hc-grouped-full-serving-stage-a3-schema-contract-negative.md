# Qwen3.8 Flash-Next grouped serving stage A3 qualification result

Date: 2026-08-31
Status: schema-harness contract negative before tensor work

A3 fixed the silent shell exit and reached the accepted-package import gate.
It then failed closed because the A2 inspector required both the accepted and
candidate native extensions to expose and map the grouped operator. The
accepted package predates that operator; adding it is the candidate's purpose.
Thus exact full-schema equality was impossible by construction.

The run performed four-card discovery and imported the accepted extension, but
ran no device tensor test, loaded no model weights, and did not reach the
candidate import. Evidence is preserved at
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/grouped-serving-stage-eeee7d6-a2-qualification-a3`.
The accepted-schema log SHA-256 is
`99d5f59b9bf65fb8ac14b60eb5a27fe279b3238fe5e223522f1c38e385ee4add`.

A separate diagnostic import established the correct frozen relationship:
the candidate preserves all 32 accepted `_xpu_C::` schemas without removal and
adds exactly 14 schemas from the pinned four-commit kernel chain, including the
single grouped interface under test. GDN retains its exact 23-argument ABI.
A4 replaces only the impossible inspector contract with this exact additive
contract, retains the A3 shell correction, and uses a fresh evidence path. A3
authorizes no retry, endpoint, speed, quality, or promotion claim.

