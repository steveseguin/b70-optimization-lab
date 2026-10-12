# Independent metric review

The root reviewer checked the suite agent’s implementation against the repository rules and historical table accounting. The first version conflated a variable-length early-EOS rate with the requested fixed64 window. That finding is fixed: both are now separate, and terminal EOS event64 is counted in the fixed64 field. The 100-event metric uses 99 intervals.

Each prompt yields one rate; median aggregation happens after those rates are computed. The helper’s primary metric is the median of prompt-class medians. Repeats have separate summaries. A 128-token cap is insufficient for the full publication gate, even when all100 events exist. See the source-bound JSON and the asymmetric hand-computed tests.
