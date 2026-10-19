# Packet58ame owner-directed offline smoke recovery

The October 19 packet58ame brief explicitly says: "If S0 and S1 are exact,
the v5's smoke precondition is satisfied by the recovered smoke."

This applies only to `packet58amd-demand-smoke-A`. Recover through the real
report functions, bind every retained smoke input by hash, verify the unchanged
`iq3-p49-split32-v1` oracle for all 12 requests in each view, and preserve the
failed outer window and queue receipts. Recovery performs no device work.

The original demand report's cross-session overhead check failed. Its
`overhead_qualified=false` and `smoke_passed=false` remain unchanged. The owner
instruction above replaces that overhead admission requirement for this exact
recovered smoke only. It is not an overhead pass, a speed result, a relaxed
oracle, or promotion evidence. V5 retains its matched warm-control performance
gates, fresh queue identity, measured storage reservation and live safety gates.
