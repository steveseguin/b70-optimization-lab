# Packet 15 non-GEMV candidate: the failing gate measured the wrong authority (2026-10-11)

Packet 15 (`experiments/own-xpu-runtime/stage2/packet15-nongemv`, commit
144f904ff4) delivered parallel SYCL replacements for every non-GEMV site of the
IQ3 Flash-Next decode step and reported 12 of 72 CPU fixtures failing. The
candidate was correctly left unqualified.

Reading the failures: the fixtures' expected bytes come from
`stage2/packet1b/reference.py`, a torch reference (`torch.rsqrt`,
`torch.sigmoid`, vector `exp`/`log`). That reference is the pre-rebase Python
path. The frozen runtime arithmetic identity v1
(`notes/2026-10-11-iq3-arithmetic-authority-decision.md`, packet3-runtime-oracle
README lines 40-52, commit 9ee12b3527) is the packet 4 nonlinear core:
scalar FP32 libm, `1.f/std::sqrt`, `sigmoid = 1/(1+exp(-x))`, PLE accumulator
rounded to BF16 before SiLU. The packet 13 CPU mock reproduced 48/48 oracle
layer hashes against that identity (commit 1c9af40c1e). Packet 15's own
elementary census (`math-probe.json`) already showed C++ libm and torch differ
in `log`, `sqrt` and `sigmoid` for some inputs, which is exactly the gap a
gate on the superseded reference would report.

Decision: the gate is re-targeted onto the packet 4 core (Codex job
`p15fix`), expected bytes regenerated from the same synthetic inputs, packet 1b
kept as a diagnostic column only. Tolerances are not relaxed and the oracle is
not changed. Open risk that the card-3 window must settle: device math library
`exp`/`log` may differ from host glibc. Because the packet 4 interpreter also
runs on the device, the decisive device gate is packet 15 kernels versus the
packet 4 interpreter on the same card and inputs, plus the first-token run's
token/hash comparison against the CPU oracle.
