# Qwen3.8 Q8_0 + external Q4_0 MTP2 strict result

Status: **qualified one-B70 short-context package headline**.

The Q8_0 target and same-model external Q4_0 MTP draft fit on one 32 GiB B70
with a 1,024-token configured context. MTP1 and MTP2 both passed the complete
fixed twelve-prompt, six-class, 512-cap cold-response suite, cache-zero gate,
objective canaries, positive draft-counter gate, and complete-token comparison
against the frozen Q8 target-only oracle. MTP2 won and was repeated on a
second fresh server.

| mode | strict class-balanced decode | samples | target exact | disposition |
| --- | ---: | ---: | ---: | --- |
| MTP0 | 19.582597 tok/s | 1 | 12/12 | matched 1K control |
| MTP1 | 30.260758 tok/s | 1 | 12/12 | valid screen |
| MTP2 | **37.062028 tok/s** | 2 | **24/24** | qualified winner |

The MTP2 attempts were `36.848184` and `37.275873 tok/s` (1.154% relative
range). Their median is **89.26% faster** than the configuration-matched MTP0
control. Both MTP2 attempts produced the same twelve complete arrays as each
other and as MTP0. This is a short-context single-user result only; it does not
fill the 32K or concurrency cells, and no value is interpolated or extrapolated.

Evidence:

- [structured aggregate](../data/2026-08-27-qwen38-q8-q4mtp-tp1-mtp2-strict-r1-result.json)
- [preregistration](../data/2026-08-27-qwen38-q8-q4mtp-tp1-depth-screen-r1-prereg.json)
- [matched-control amendment](../data/2026-08-27-qwen38-q8-q4mtp-tp1-depth-screen-r1-control-amendment.json)
- [read-only validator](../scripts/validate-20260827-qwen38-q8-q4mtp-tp1-mtp2-strict-r1.py)
