# Qwen3.8 Flash-Next FP8 97-weight HC-up authority result

Date: 2026-08-31
Status: production authority frozen

The control-only census passed. It loaded the 97 MTP0 target hyperconnection
up weights in production order, generated a distinct deterministic BF16 input
for each slot, and obtained one finite exact `F.linear` output hash per slot
across ten complete sweeps. No grouped candidate was imported or invoked.

The 97-entry weight manifest digest is
`da68ed6ed1fa5dba536bd5881799972c6ce079a55a2ca82e1ec8832520a8a5f7`.
The resulting `(slot,input,output)` authority manifest digest is
`78d773b0a4387e2396828c3b360983ab79051f871065377aaf8dba3ef3b1c91e`.
The raw evidence is 15af5344c259fa83ffc16ca1755c621a83cce01651119b2c5234c4276a2fcab9
at the path recorded in the
[structured summary](../data/20260831-hc-m1-grouped-gemm-round-robin-authority.json).

The control bank occupied 635,798,528 XPU bytes, consistent with the exact
635,699,200 bytes of weights plus small runtime allocations. Host memory and
swap remained healthy. This is a correctness oracle only: it authorizes the
separately preregistered full-bank component comparison, not source
integration, endpoint performance, or deployment.
