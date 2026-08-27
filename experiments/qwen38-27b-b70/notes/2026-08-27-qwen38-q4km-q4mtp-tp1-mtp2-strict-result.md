# Qwen3.8 Q4_K_M + Q4 MTP2 TP1 strict result

The qualified one-B70 headline is **42.636988 tok/s**, the median of two
fresh-server full-suite values (`42.600910`, `42.673065`). Both runs used the
fixed twelve-prompt/six-class suite, a 512-token natural stop/length cap,
cache disabled and zero on every request, returned raw token IDs, the
conventional 99 intervals between events 1–100, and the objective canary
battery. Relative range was `0.169%`.

The matched target-only control measured `27.375682 tok/s`, making the MTP2
gain **55.75%** under the same target, binary, launch stack, workload, and
arithmetic identity. All twelve complete arrays matched between both MTP2
servers and the target-only control. The final attempt accepted `3429/5132`
draft tokens (`66.8%`) across the performance suite plus canaries.

| depth | strict screen tok/s | gain vs MTP0 | complete target match | decision |
| ---: | ---: | ---: | ---: | --- |
| 0 | 27.376 | — | 12/12 | matched control |
| 1 | 38.320 | +40.0% | 12/12 | valid |
| 2 | **42.601** | **+55.6%** | 12/12 | winner; replicated at 42.673 |
| 3 | 42.123 | +53.9% | 12/12 | valid, slower |
| 5 | 32.241 | +17.8% | **0/12** | rejected |

MTP5 changed all twelve complete outputs, including divergences at generated
tokens 1–333, despite passing objective canaries. It is not promoted. The
first MTP2 attempt is also preserved but excluded: the runner was amended
while its shell was live and exited before canaries, so its diagnostic value
cannot enter the decision.

This result covers short-context, one-user TP1 only. Exact 32K and
output-qualified concurrent-serving profiles remain unmeasured for this exact
MTP2 deployment and must not be copied from the target-only package.
