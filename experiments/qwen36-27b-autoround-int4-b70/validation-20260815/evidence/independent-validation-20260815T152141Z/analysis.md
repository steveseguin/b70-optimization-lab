# Independent Qwen3.6 27B INT4 validation result

- strict validation passed: **False**
- all arms valid: `True`
- all speculative outputs target-exact: `False`
- all same-identity repeats exact: `False`

## Current-accounting speed

| Arm | Mode | Pair | Selection median | Holdout median | Combined median |
| --- | --- | --- | ---: | ---: | ---: |
| `nospec-01a` | nospec | `0,1` | 48.153 | 47.827 | 47.868 |
| `spec-01a` | spec | `0,1` | 94.728 | 103.925 | 98.771 |
| `nospec-23a` | nospec | `2,3` | 48.013 | 47.986 | 48.006 |
| `spec-23a` | spec | `2,3` | 94.650 | 104.288 | 101.078 |
| `spec-01b` | spec | `0,1` | 95.962 | 104.546 | 98.353 |
| `spec-23b` | spec | `2,3` | 94.531 | 104.388 | 98.761 |

## Candidate aggregate

- selection: median of four arm medians `94.689` tok/s (range `94.531`–`95.962`); prompt-bootstrap 95% interval `88.555`–`100.715`.
- holdout: median of four arm medians `104.338` tok/s (range `103.925`–`104.546`); prompt-bootstrap 95% interval `98.707`–`110.902`.
- combined: median of four arm medians `98.766` tok/s (range `98.353`–`101.078`); prompt-bootstrap 95% interval `92.969`–`104.754`.

See `analysis.json` for row groups, quality, parity, acceptance, and errors.
