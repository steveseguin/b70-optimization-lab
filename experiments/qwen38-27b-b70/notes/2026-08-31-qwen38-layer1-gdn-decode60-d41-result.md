# Qwen3.8 layer-1 GDN token-60 stage trace D41 result

D41 found the first internal late-decode difference at the recurrent core:

| Stage | Unique hashes |
| --- | ---: |
| hidden input | 1 |
| QKVZ projection | 1 |
| BA projection | 1 |
| recurrent core before norm | 4 |
| output gate | 1 |
| gated norm / flattened | 4 |
| output projection | 4 |

Thus all loaded INT4 projections entering the core are exact at true M=1. The
remaining source is the recurrent state entering call 62 or the in-place core
update/ordering itself. D42 hashes convolution and SSM state immediately before
and after the target core call. Its deliberate pre-core synchronization makes
it a state/ordering diagnostic, not a performance candidate.
