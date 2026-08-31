# D59 preregistration: repaired TP2/MTP0 strict qualification

Date: 2026-08-31

The repaired TP1/MTP0 lane is now exact across four traced processes and two
complete strict suites. D59 moves the same M=512/no-barrier projection repair
to both local B70 ranks at TP2, still with MTP disabled and eager execution.

The run uses GPUs 0 and 1, a fresh cache, local ext4 weights, prefix caching
disabled, all 12 varied prompts exactly once, cached tokens zero, natural EOS
handling, objective canaries, and bounded fault/shutdown checks. All complete
token-ID sequences must also match qualified TP1 D54. This deliberately strict
cross-TP requirement prevents a faster collective layout from silently changing
greedy outputs.

If TP2 fails to start or fit within the 13 GiB host-memory/36 GiB memory+swap
container bounds, that is a captured local-host support result rather than
permission to raise unbounded memory. A pass authorizes a second fresh TP2
replay, then restoration of MTP depth under the same gates. The metric remains
the median of prompt-class medians; no individual prompt is a headline.
