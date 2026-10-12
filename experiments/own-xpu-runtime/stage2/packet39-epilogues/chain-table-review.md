# Independent chain-table review

Reviewer: harness agent. I did not author `CHAINS.md`. I read the recorded
packet29 `build/w2c-r29/run/plan.json` independently, counted its launch labels,
and followed `packet3/step/plan.hpp` through packet29 `main.cpp`, `adapter.cpp`,
`kernels.hpp` and `core_v2.hpp`. Source hashes and independent counts are in
`chain-table-review.json`. These are CPU reads only.

The recorded plan contains 1,777 logical sites. All common HC/expert/shared
sites occur 48 times; GDN sites 36 times; QSA sites 12 times; PLE/final/token
boundaries once. The logical census contains exactly one `moe` per layer,
whereas the timing receipt has two device launches per group: the table is
correct to split the unconditional ordered ten-expert mixture from the guarded
shared blend. Gate/up is already paired, and the extra `expsup` GEMV is absent;
its separate status check remains. No already-merged gather is counted as a
new saving. Device multiplicities come from the receipt, not the logical
plan's older `parallel_kernels` estimates.

The plan's tensor-owner variants independently confirm split-four HC low,
Q6 shared gate/up, and attention output projections. Q8 shared gate/up are
split-one. The format plan contains 47 IQ2_S / 1 IQ3_S expert gate/up layers,
47 Q6_K / 1 Q8_0 shared gate/up layers, and 35 Q6_K / 1 Q8_0 GDN QKV layers.
The final low activation is the 97th HC activation, not an extra full layer.

Two findings were sent to the table author and corrected in `CHAINS.md`:

1. The failure contract must include `ng::group`'s context-position guard:
   `pos < 0 || pos > capacity - tokens` raises sticky and suppresses outputs.
   That guard applies to activation, convolution and shared blend. The simple
   status and residual-combine bodies have active/error checks but do not
   introduce a position check themselves. Fusing shared blend and residual
   combine inherits the blend's failure and must suppress both.
2. PLE gating multiplies `gate * value`, in that operand order. Describing
   `value * gate` is insufficient for the requested exceptional-value identity,
   even though finite products agree.

The eligibility decisions otherwise follow the real dependencies. Expert
mixture needs ten completed expert rows; HC mix needs four gate rows; GDN gated
needs the recurrent-output normalization reduction; QSA prepare/pool/select and
argmax need other rows. None is an unchanged-body row epilogue. GDN convolution,
in contrast, has four independent taps of already stored per-channel history
plus its own QKV row and can be appended after the GEMV BF16 round without a
new cross-row dependency. Its in-place history is observable and belongs in
both CPU and device byte comparisons.

I found no missing tiny-launch class in the table. The remaining one-off
PLE convolution/add opportunity is identified and explicitly separated from
this packet's GEMV epilogues. Norm post-scaling cannot move before its retained
reduction's readiness dependency. No device speed or identity result follows
from this source review.
