# Packet78 boundaries

| Arm or method | Outcome / revisit condition |
| --- | --- |
| Single-workgroup all-pairs route | CPU exact, replaced before device use because it retains 262,144 comparisons. [Source](evidence/pre-bitonic/route-all-pairs.hpp), archived receipts alongside it. No measured speed verdict. |
| Ranking raw logits | Invalid for exact order: exp and division can collapse distinct logits into probability ties. Rank rounded probabilities, then original index. |
| New floating-point reduction tree | Excluded. Keep 16-leaf route sums and the original padded HC tree and BF16 boundaries. |
| CPU plan with no real startup | Insufficient. Retain full allocation/capture, post-load draft setup and actual captured selection-consumer checks. |
| Lane-A winner as record | Insufficient. Lane B must test the exact improving best view between fresh controls; full qualification follows separately. |
| CPU seal as speed/quality promotion | Excluded. Device parity and speed remain pending. |

[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md).
