# s192_report: expert kernel issue-floor decomposition (diagnostic, never a speed result)

verdict: measured

| kernel | cold us | warm us | no-load us | warm/cold | no-load/warm | verdict |
|---|---|---|---|---|---|---|
| gateup | 73.75 | 46.35 | 44.69 | 0.629 | 0.964 | instruction-issue bound: only an instruction diet can move the class |
| down | 45.94 | 33.75 | 33.33 | 0.735 | 0.988 | instruction-issue bound: only an instruction diet can move the class |

layer-equivalent (cold): gate/up 73.75 + down 45.94 = 119.69 us vs copy floor 37.36 us

follow-on bars (candidate must be <= 0.85 x production in both orders and every stratum):
- exp-diet (gateup): cold bar 62.69 us, warm bar 39.40 us (kernel)
- exp-act-epilogue (gateup): cold bar 67.29 us, warm bar 44.01 us (kernel + expsact launch)
- down-diet (down): cold bar 39.05 us, warm bar 28.69 us (kernel)
