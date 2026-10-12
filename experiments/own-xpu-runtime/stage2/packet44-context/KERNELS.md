# Capacity-aware kernel registration

Dispatch names and numerical kernels are inherited from packet38. ng::Shape
adds an independent extent. Allocation bounds and cache strides remain C;
selection/attention launch ranges use min(C,round_up(n,32)), capped at2051
admitted positions for attention. True n still determines all reduction trees.
Pool work is constant for one-token decode and maps to newly completed blocks.

Packet42 measured a 0.5–1.5us launch floor and several-microsecond penalties from
unused groups, barriers and local memory. Early-returning C-sized grids would
still charge short requests for reserved capacity. This packet therefore
re-prepares only selection/attention launches at 32-position boundaries.

| Capacity | Timed lengths (no ranges) |
| --- | --- |
|256|88,104,120,136,152,256|
|4096|88,152,1024,2048,2049,4096|
|32768|88,152,1024,2048,4096,8192,32767|

At each length K2 covers QSA preparation, pooling, selection and attention. Its
attention selection comes from the independent arithmetic-v2 core. The selected
candidate must pass at every registered length; no pooled win can hide a loss.
K1 checks the same grid against the reference, independently on two fresh owners.
Every repetition is compared exactly; compact output length/SHA256 records avoid
writing the same full-capacity pool thousands of times. CPU output hashes are
sealed separately per allocation capacity.

Beyond-budget CPU fixtures additionally test2047,2048,2049,2051,2052,4095,4096,
8192 and32767 with ties and nonfinite guards. See capacity-selection-gates.json
and independent review-selection.md. Inactive score scratch beyond the launch
extent is unspecified; selected scores, probabilities, output BF16 layer bytes
and control status retain their exact contract.

Argument guards remain at1024 bytes. Precision flags apply to compilation and
linking. No device binary has been executed by this packet's preparation agent.

The copied attention dispatch remains `p30.attention.sg32`, with the same
arithmetic body and runtime cache stride at every capacity. The optional P33
attention candidate has fixed 128/256 specializations and uses its existing
generic body for larger capacities; K2 measures it under the same all-length
selection rule. Existing P33 GEMV selections are independent of context
capacity. No measured short-context wall-time claim is made before the windows.
