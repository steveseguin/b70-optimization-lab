# Packet58q interpretation boundaries

| Closed interpretation | Evidence / revisit condition |
| --- | --- |
| Production's regression is more expert misses | All five arms have identical counts/bytes at all 2,386 positions. Revisit only with new unmatched-route/cache evidence. |
| Only tile16 uses pinned expert backing | Both layouts allocate pinned banks; their sparse lookup path is unchanged. Do not infer backing from RssAnon. |
| Tight production controls prove the candidate had matched page state | Both 58n controls fault heavily; tile16 does not. Require measured state and matched independent timing before causal attribution. |
| GPU/zero-copy time is zero, or can be recovered from bandwidth | Profiling is disabled; placeholders and fixture-derived estimates are not model measurements. |
| Pre-read model files to protect the record | Existing lane rules forbid warming pages. Preserve sealed load order, actual fault costs and all windows. |

[Analysis](ANALYSIS.md) · [CPU closeout](CPU-ANALYSIS-CLOSEOUT.md).
