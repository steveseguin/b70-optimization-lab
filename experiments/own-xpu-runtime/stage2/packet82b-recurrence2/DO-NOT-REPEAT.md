# Packet82b boundaries

| Arm / method | Decision | Revisit condition |
| --- | --- | --- |
| Add rec-gates to rec-parallel | Already present. rec-both is an alias/null control; cannot win. | A genuinely distinct source delta. |
| Packet67 rec-head prepass | Closed: extra launch and global scratch; preserve original negative results. | Evidence eliminating those costs. |
| Drop remaining preparation/inter-token barriers | Excluded: producers share SLM and subsequent tokens reread rounded state. | A complete replacement dependency proof. |
| Change reduction order, gate math or BF16 boundaries | Excluded by arithmetic identity. | Owner's separately labeled quality decision. |
| CPU fixture as device exactness or speed | Invalid. | Exact pinned device screens and subsequent promotion gates. |
| Tiny allocation-only mock | Insufficient: full-shape startup and actual operation consumers required. | None. |

See [analysis](ANALYSIS.md) and the CPU preparation closeout for evidence.
