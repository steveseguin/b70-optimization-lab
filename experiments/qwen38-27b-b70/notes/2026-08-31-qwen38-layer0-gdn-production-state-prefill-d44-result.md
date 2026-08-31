# Qwen3.8 layer-0 production GDN state after prefill D44 result

D44 clears the packaged layer-0 GDN attention call as the first prefill drift
boundary. Across four fresh processes, both its M=71 input and returned output
were byte-identical. The output SHA-256 was
`3729d249f89fbc2e524935349eecbfcad743f1fc29295b90273fcad900170f38`,
the same value observed in D39.

The generic result therefore correctly classified the boundary as
`negative-bound-after-layer`; all four full responses still first differed at
generated token index 60.

The whole-cache state hashes had two shapes and two hashes because one process
allocated 115 cache slots while the other three allocated 114. Those hashes
include inactive/uninitialized slots and are not comparable state evidence.
They do not weaken the decisive production input/output result.

Together with D43's four-way divergent input at layer 1, this moves the first
prefill drift boundary into the remainder of decoder layer 0: post-attention
residual/normalization or the dense MLP. D45 brackets those stages.
