# Qwen3.8 Flash-Next FP8 TP4 MTP0 PLE-only A10 result

Date: 2026-08-29
Status: rejected at exact-4K repeat gate; A9 remains Grade C

A10 was the separately started, frozen replica required by the A9
preregistration. It repeated the same model, source, staged runtime,
TP4/EP4/eager/MTP0 topology, 4,352-token capacity, 128-MiB cache, and PLE-only
UVA placement. All four ranks again offloaded exactly 11.92 GiB, model loading
again reported 31.57 GiB/card, and the cache exposed the predicted 4,747
tokens. The recovery canary, 6/7 established semantic boundary, 16/16 fixed
repeat, and exact cache-zero 4K needle all passed.

All three short rows matched the protected short output hash. They measured
`5.378285`, `5.317771`, and `5.465797 tok/s`, a diagnostic median of
`5.378285 tok/s`, 2.96% above the protected current-runtime placement. This
confirms that the PLE-only fit retains its useful speed shape, but it does not
qualify the recipe because the later required gate failed.

The two byte-identical p4096/o128 requests each passed every transport gate:
exact 4096/128/4224 usage, zero cached tokens, length stop, 128 returned token
IDs, and valid 100-event/99-interval timing. Row 1 measured `5.270154 tok/s`
with `107.919 s` TTFT and matched retained output authority
`1d833e5f...39d5cc`. Row 2 measured `5.163408 tok/s` with `104.832 s` TTFT
but returned `f9ba2586...8fe20`. The arrays first differ at zero-based generated
token index 7 and then differ in 119 of 128 positions.

The client therefore failed closed before writing a passing summary. The
supervisor terminated the owned server and recorded final status 143. No model
process, listener, or device allocation remained; all four cards returned
below 43 MiB. The shutdown-time API output-handler message and one shared
memory cleanup warning are retained. The bounded journal contains no
B70-addressed event, but it has three corrected APEI/NVMe receiver records for
the local NVMe and therefore does not earn clean-host wording.

This result does not show that PLE-only placement caused the divergence. A7
already produced the same exact-4K repeat failure under the older selective
placement, while A9 returned the authority twice with PLE-only placement. It
does prove that PLE-only A9 cannot be promoted as a reliable or lossless base.
A9 remains an additive Grade-C same-server speed screen, all protected scores
remain unchanged, and A10 is retained as the required fresh-server bounded
negative.

The next admissible GPU arm is a lighter report-only exact-4K diagnostic using
the serving API's existing generated-token top-score data. It must use the
same frozen prompt, greedy settings, and PLE-only server identity, receive no
speed credit, and stop after enough bounded repetitions to capture the first
different decision. Do not reapply the A8 worker trace that preceded the host
freeze. Do not grant MTP0 tuning promotion credit until exact repeated output
is restored.

Structured receipt:
[`../data/20260829-tp4-mtp0-4352-ple-only-a10-fresh-server-negative.json`](../data/20260829-tp4-mtp0-4352-ple-only-a10-fresh-server-negative.json).
