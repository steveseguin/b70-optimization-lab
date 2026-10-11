| Class | Runtime R5 kernel | In-model us/group | R5 us | Selected | Conservative ms/token saved | Baseline within 15% |
|---|---|---:|---:|---|---:|---|
| expsgate | integrated::experts/iq3::kopt4::expert_gate_up(split=1) | 177.9206349206349 | 171.406 | p28.paired.wg32 | 4.2501 | True |
| gdn.qkv | integrated::dense/expanded_sg32_v1 | 100.65079365079364 | 93.07249999999999 | p28.dense.wg32 | 0.8512 | True |
| attention | integrated::dense/expanded_split4_v1 | 66.74074074074075 | 58.334 | p28.dense.wg32 | 0.6950 | True |
| logits | integrated::dense/expanded_sg32_v1 | 2136.4761904761904 | 2446.432 | p28.dense.wg32 | 0.5423 | True |
| gdn.z | integrated::dense/expanded_sg32_v1 | 62.02601410934744 | 56.979 | p28.dense.wg32 | 0.4800 | True |
| qsa.qgate | integrated::dense/expanded_sg32_v1 | 118.00066137566138 | 113.80199999999999 | p28.dense.wg32 | 0.3187 | True |
| hc.f.gate | integrated::dense/expanded_sg32_v1 | 29.5021164021164 | 26.875 | p28.dense.wg32 | 0.2900 | True |
| hc.a.gate | integrated::dense/expanded_sg32_v1 | 29.34232804232804 | 26.875 | p28.dense.wg32 | 0.2900 | True |
| hc.a.low | integrated::dense/expanded_split4_v1 | 18.380588624338625 | 16.198 | p28.dense.rows4 | 0.1850 | True |
| shexpgate | integrated::dense/expanded_sg32_v1, integrated::dense/expanded_split4_v1 | 16.402380952380952 | 13.9585 | p28.dense.wg32 | 0.1550 | True |
| shexpup | integrated::dense/expanded_sg32_v1, integrated::dense/expanded_split4_v1 | 15.21957671957672 | 14.01 | p28.dense.rows4 | 0.1550 | True |
| shexpdown | integrated::dense/expanded_sg32_v1 | 15.754596560846561 | 14.219000000000001 | p28.dense.wg32 | 0.1400 | True |
| qsa.ik | integrated::dense/decode_const_split4_v1 | 10.389695767195766 | 8.854 | p28.dense.wg32 | 0.0525 | True |
| qsa.k | integrated::dense/expanded_split4_v1 | 10.814748677248678 | 9.844000000000001 | p28.dense.rows4 | 0.0312 | True |
| qsa.v | integrated::dense/expanded_split4_v1 | 10.542314814814814 | 9.896 | p28.dense.rows4 | 0.0300 | True |
| ple.key | integrated::dense/expanded_sg32_v1 | 102.61571428571429 | 92.187 | p28.dense.wg32 | 0.0243 | True |
| ple.value | integrated::dense/expanded_split4_v1 | 38.523492063492064 | 34.167 | p28.dense.wg32 | 0.0095 | True |
| final.gate | integrated::dense/expanded_sg32_v1 | 29.823015873015873 | 26.875 | p28.dense.wg32 | 0.0060 | True |
| final.low | integrated::dense/expanded_split4_v1 | 18.055555555555557 | 16.146 | p28.dense.rows4 | 0.0039 | True |
| expsdown | integrated::experts/iq3::kopt4::expert_down(split=1) | 130.12929894179894 | 125.625 | r5 | 0.0000 | True |
| hc.a.inject | integrated::dense/decode_const_split4_v1 | 18.763392857142858 | 15.417 | r5 | 0.0000 | False |
| hc.f.low | integrated::dense/expanded_split4_v1 | 19.761805555555558 | 16.146 | r5 | 0.0000 | False |
| hc.f.inject | integrated::dense/decode_const_split4_v1 | 19.37063492063492 | 15.3645 | r5 | 0.0000 | False |
| qsa.iq | integrated::dense/decode_const_split4_v1 | 16.071428571428573 | 11.458 | r5 | 0.0000 | False |
| router | integrated::dense/decode_const_split4_v1 | 20.16871693121693 | 10.8855 | r5 | 0.0000 | False |
| gdn.a | integrated::dense/decode_const_split4_v1 | 9.99885361552028 | 7.084 | r5 | 0.0000 | False |
| gdn.b | integrated::dense/decode_const_split4_v1 | 9.12200176366843 | 7.0835 | r5 | 0.0000 | False |
| shared_gate | integrated::dense/decode_const_split4_v1 | 8.910185185185187 | 6.667 | r5 | 0.0000 | False |

Rows with a baseline mismatch do not measure representative runtime cost and cannot change dispatch. Savings are conservative fixture accounting, not measured model throughput.
