# Packet126: earlier guessed-token draft, CPU dependency audit

Scope: the owner's 2.5-hour CPU-only task. The immutable starting source is
packet124's bundle8 BASE: bundle7's native runtime with the host drain repair.
Target arithmetic is `iq3-p49-split32-v1`; the draft remains on rank1 with
packet114's fixed 80,128-row prefix and packet105b's target head split.

`git pull --rebase` refused the unrelated dirty orchestration files. After
`git fetch origin`, HEAD and origin/main both were
`8b7394cfb106db3585b54f3766af1da99c4ac9b7`. Those edits remain untouched.
The host is steve-b70s; initial root free space was 35.12 GB, above this task's
25 GB floor. No GPU, service, sudo, power/memory/swap/cache change or reboot is
authorized here. CPU programs use nice19, CPUs8–15/24–31, Python `-B`, closed
stdin and at most8 GiB; no runtime program inherits a resource cap.

The first milestone preserves the accounting method and current source and
trace inputs. Packet108's extractor and packet85's position-join helper are
copied without editing. Only their accounting function ASTs will execute;
their old module-level resource-cap statements will not execute on import.
Both complete packet118 composite candidate summaries are the timing inputs.

Initial source finding: rank0 finishes its speculative half before servicing
the target suffix; rank1 cannot return its verified token until that service
finishes. The suffix service is absent from `rank_trace`, while rank1's wait
for it is inside the target command. Earlier draft execution can only save
rank1 compute-engine time if it fills a real dependency wait; moving serial
draft and head work alone does not remove either cost. Misses must restore
the draft's private mutable state before recomputing with the verified token.
The result and admission decision will be recorded after the simulation.

[Packet analysis](../experiments/own-xpu-runtime/stage2/packet126-early-draft/README.md).
