# s58dm_report: exact instruction-diet micro of the one-card record gate/up kernel (diagnostic, never an engine speed result)

verdict: measured

| stratum | gate | production us (p10/p90) | candidate us (p10/p90) | ratio A/B | ratio B/A | <= 0.85 |
|---|---|---|---|---|---|---|
| cold | yes | 73.18 (72.50/73.75) | 57.24 (56.35/57.71) | 0.779 | 0.785 | yes |
| warm | yes | 48.91 (48.65/49.27) | 36.88 (36.56/37.50) | 0.753 | 0.755 | yes |
| warm-direct | info | 48.59 (48.44/49.06) | 36.56 (36.46/37.19) | 0.754 | 0.751 | yes |
| warm-real-layer0 | info | 48.02 (47.71/48.33) | 36.12 (35.94/36.67) | 0.755 | 0.749 | yes |
| warm-real-layer24 | info | 48.07 (47.81/48.44) | 36.20 (35.83/36.46) | 0.751 | 0.755 | yes |

p58-diet: qualified: <= 0.85 x production cold and warm in both orders; saved 15.94 us/layer cold, 12.03 us/layer warm; one-card projection +2.80 % (cold) / +2.11 % (warm) at 2 % per 11.4 us
- control cold: interleaved production 73.18 us vs fresh production-only 73.23 us (0.1 %)
- control warm: interleaved production 48.91 us vs fresh production-only 48.96 us (0.1 %)

NaN payload-order-only rows on NaN-only strata (diagnostic, never a kill): 2
