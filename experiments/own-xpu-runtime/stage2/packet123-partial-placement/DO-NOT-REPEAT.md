# Packet123 boundaries

- [Slack closeout](SLACK-CLOSEOUT.md): placement admission is unproven.
- Do not call bundle7's 0.482640 ms command tail usable rank0 slack. The
  split-head suffix executes outside the rank trace, and rank1 waits for it.
- Do not call outside-command time GPU idle. It includes untraced work.
- Do not claim measured slack <0.3 ms; that is also unsupported.
- Do not substitute packet103's control or packet108's old no-split-head
  budget for bundle7, or subtract historical head micro times as if current.
- Do not infer missing timing from empty event files or from transfer sizes.
- Revisit only with head-service and head-readiness timestamps bound to the
  current bundle's intervals, then redo the ≥0.3 ms admission.
- No partial placement, device run, compiled candidate, queue proposal or
  output/speed qualification exists in this packet.
