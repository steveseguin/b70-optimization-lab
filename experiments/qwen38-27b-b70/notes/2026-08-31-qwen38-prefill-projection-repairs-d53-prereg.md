# D53 preregistration: medium-prefill projection repairs

Date: 2026-08-31

This causal repair screen is preregistered after two D52 traces and before D52
completes. Those traces agree through layer-3 input normalization, differ at the
packed INT4 QKV projection, reconverge to an identical raw and gated attention
result, and differ again at the INT4 attention output projection. D47/D48 had
already shown the same M=71 arithmetic problem and M=512 repair for dense MLP
down projection.

D53 keeps the frozen image's GDN projection repair, pads only these additional
medium-width (`32 < M < 512`) prefill projection roles to M=512, and slices the
real rows back:

- every dense MLP down projection;
- every full-attention packed QKV projection;
- every full-attention output projection.

Decode widths are outside the branch. Four fresh TP1 processes on GPU 0 use the
local ext4 model, frozen image, eager execution, prefix caching disabled, and
separate cache roots. Every decoder input/output/residual at prefill call 2 is
hashed. Exact boundaries and one complete response class are necessary to move
to strict varied-prompt qualification, but this one-prompt synchronized screen
is itself neither a performance nor a quality claim. If a boundary still
diverges, the earliest layer/stage becomes the next localization target.
