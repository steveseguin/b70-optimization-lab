# Qwen3.8 final-hidden trace D9 result

D9 is a **positive causal finding**. All four fresh TP1 eager processes had the
same call-60 input token ID and MRoPE positions, but all four complete final
hidden-state hashes differed. Processes 1–2 selected token `9447`; processes
3–4 selected token `10342`. This exactly reproduced the strict repeat's first
branch at zero-based output position 60.

| process | final hidden SHA-256 | token 60 |
| --- | --- | ---: |
| 1 | `32cc42dd32f614c701fcae7b7dc3b34ea545530864dfd681035236932b5b7f6b` | 9447 |
| 2 | `d83b447c6ee7fc1f13f3987fe2916f8b050ad9e35c2d80eed880549744015b20` | 9447 |
| 3 | `1cac93f92142031e02d36fcc6aa261cfd35fc8944c251e009fa15963dfebaa10` | 10342 |
| 4 | `4701991e7becf14c3959fc631dd82795ecf6f81170ed221d43263a61e0dc60c5` | 10342 |

The input-ID hash was
`51525844d3da2a4a742a91b5c0bf89d3e6026487a83a3bfe8abd1e677a3938f9`
and the position hash was
`34bc8556a8bf515db1f72f506680d0687cb5deeed52276f22a4fac834fec7640`
in every process. Cached prompt tokens were zero. Only call 60 was
instrumented, after the model forward, so the preceding inference was not
serialized by the diagnostic.

This localizes the defect to the decoder/final-norm path before the LM head and
sampler. The next step is a decoder-layer binary search at the same request and
call. No performance result is promoted.
