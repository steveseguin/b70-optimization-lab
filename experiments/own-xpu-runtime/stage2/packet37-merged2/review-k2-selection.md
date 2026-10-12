# Independent K2 selection review

Reviewed the candidate aggregation, measured incumbent mapping, heavy-buffer rotation,
registry closure, and fusion resolver without running a device binary.

Found and fixed with the K2 author: small.hc priced only the attention HC site while
also replacing the independently selected FFN HC site. Equal geometry does not imply
equal measured costs or selected implementations. The resolver now prices both sites
separately and keeps the fusion only when it beats each site's selected low+inject
sum. The compatibility alias hc.low is not counted as a third operation.

All 13 CPU selection tests pass, including the new differing-site regression,
sum versus individual cost, ties, missing measurements, all-format wins, NaN
rejection, failed byte checks, and registry/incumbent coverage. The one-card K2
harness retains 200 measured repetitions and eight full payload copies above
8,000,000 bytes, with untimed preflight/postflight comparisons. The incumbent is
measured again beside each candidate. Fusion comparison consumes selected member
costs, and its final dispatch is emitted for both ranks with the explicit single-card
measurement limitation. Source hashes are in review-k2-selection.json.

CPU inspection cannot establish GPU equality, timing, or whether these choices win
on either rank. K1/K2 remain coordinator windows.
