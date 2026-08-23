# Ornith 1.5 35B-A3B: host polling endpoints are neutral

Date: 2026-08-23 EDT

Status: **CLOSED NEUTRAL — retain default poll=50**

The accepted one-card recipe had not explicitly screened llama.cpp's host poll
percentage. A same-binary depth-zero `tg128`, seven-repetition ladder tested
the default around both endpoints in order `50 / 0 / 100 / 50`:

| Poll | Decode (tok/s) | Within-run standard deviation |
| ---: | ---: | ---: |
| 50 control A | 133.340583 | 2.100617 |
| 0 | 133.501514 | 1.636342 |
| 100 | 133.311530 | 1.727572 |
| 50 control B | 133.225629 | 1.839923 |

The two default controls average 133.283106 tok/s. Poll=0 is +0.164% and
poll=100 is +0.021%, both far below the observed within-run spread. No serving
or correctness escalation was justified, and the packet retains the default
poll setting. Raw engine records are under `../data/ornith-poll-*`; the
structured decision is `../data/2026-08-23-ornith35b-poll-summary.json`.
