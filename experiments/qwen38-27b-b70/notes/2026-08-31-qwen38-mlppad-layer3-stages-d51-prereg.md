# D51 preregistration: repaired-MLP layer-3 stage split

Date: 2026-08-31

This is a causal determinism diagnostic, not a performance or quality claim.
D50 localized the first repaired-model decoder divergence to layer 3: its input
was identical and its returned hidden state was not. The dense-MLP M=512 repair
remains active in all layers. D51 reconstructs only production layer 3 at
prefill call index 2 (71 tokens) and hashes, with synchronization induced by
each device-to-host snapshot:

1. decoder input;
2. input-normalized hidden state and residual;
3. full-attention output;
4. post-attention-normalized hidden state and residual;
5. repaired dense-MLP output.

The run uses four fresh TP1 processes on GPU 0, the frozen local ext4 model,
the same frozen image as D50, eager execution, prefix caching disabled, and the
frozen `sql-debugging` screening request. Any boundary with multiple hashes is
a positive localization finding. Identical complete text does not override an
internal hash split. No speed from this synchronized diagnostic is publishable.
