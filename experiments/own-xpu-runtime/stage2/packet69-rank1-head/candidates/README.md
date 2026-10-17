# Packet69 candidates

Source copies start from frozen packet64-record-bundle. Relative includes move
one directory deeper; parent arithmetic objects are referenced by hardlink and
hash. Only the engine entry, selection implementation and new head translation
unit are rebuilt. No model or GPU ran during preparation.

| View | Target head | Draft head | Draft QSA | Draft HC |
| --- | --- | --- | --- | --- |
| production | production | production | production | production |
| target-wide64 | wide64 | production | production | production |
| target-wide128 | wide128 | production | production | production |
| draft-head-wide64 | production | wide64 | production | production |
| draft-attention | production | production | target split32 | production |
| draft-hc | production | production | production | packet64 draft-HC group |
| combined | wide64 | wide64 | target split32 | packet64 draft-HC group |

The new head kernel loads eight int8 weights and eight BF16 inputs at a time.
Each lane still evaluates exactly the same eight multiply-then-add operations
per tile, visits tiles in the same order, and uses the original ascending-width
32-lane tree. WG64/WG128 pack two/four independent row subgroups; no row's
reduction is split or reassociated. It writes the original BF16 logit array,
then the unchanged argmax chooses the token with the unchanged tie rule.

Draft attention selects the existing implementation 12, the target split32
kernel. Draft HC uses the existing independently selected packet59 low,
gate/mix and injection choices from packet64's draft-HC view. It does not
silently change other draft sites. The six candidates and control share one
binary; all choices are parsed once before command capture.

[CPU gates](evidence/cpu-gates.json): GNU and Intel agree exactly on 512
production-K head fixtures, all FP32 lane sums, final FP32 sums and BF16
outputs. WG64/WG128 cover ragged and full/prefix row counts. Draft split32 and
HC operator fixtures agree in two fresh processes under each compiler.
These are small operators, not CPU model runs. [Linked parser gate](evidence/selection-gate.json)
accepts all seven views and rejects four malformed/unauthorized choices.

[Quick lane commands and comparison](../screen/quick/README.md).
Full target output, fresh-device determinism, draft acceptance and speed remain
pending. Packet49 is the device oracle. Production remains the default.
