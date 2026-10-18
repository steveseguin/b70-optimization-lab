# Packet116 one-load QSA schedule bracket

This is a separate packet111r (`9b49c03e7`) bundle copy. Both views retain its
combined head split and other fusion. The only runtime change is
`qsa_schedule=production|p116`; the draft and every storage layout stay fixed.

The proposed lane-B job loads one rank pair and runs control / candidate /
control / candidate / control. Each view runs incident64 and all twelve
128-token requests, checking every output against `iq3-p49-split32-v1` and
requiring cold request state. It preserves allocation identities, does no
weight upload between views, and re-captures QSA commands after each switch.
Expected duration is 9–15 minutes; the watchdog is 3,600 seconds, at least
four times the upper estimate. This screen is not a fresh-server record gate.
Every view must have identical per-prompt acceptance, and control drift must
stay within 3%. The screening qualification requires both candidates to beat
the strongest control by at least 0.5%; completion alone is not a speed win.

The launcher rereads both fresh-process micro receipts and the current micro
binary/seals before any admission. Both context128 attention-plus-selection
ratios must be at most 0.6; context4096 must also be reported. Missing, changed,
inexact or slow evidence refuses the bracket. The coordinator supplies the
device authorization, fault review and normal lane/memory admission.

CPU gates cover only production and p116: both ranks' real-size allocation,
capture/switch/reset checks and eleven startup/host-reference paths per view.
Miniature reset and IPC checks explicitly project the target head to production
and expert storage to wide64, because those existing full-size layouts refuse
miniature shapes. These checks test reset/transport; separate real-size QSA
byte gates qualify arithmetic. Device-entry imports preserve inherited limits;
both actual native exec points reject finite address-space caps.

The CPU capture fixture adds explicit serializers for the inherited p60 HC
and p109 shared-down capacity fields, p105's row/offset pair, and the banked
small-GEMV shape array. The original
registry omitted these fields. Unknown functors still refuse. This audit
extension changes no runtime operation or model arithmetic; the first refusal
and its CPU backtrace remain in `evidence/`.

Preparation uses `nice -n 19 taskset -c 8-15,24-31 python3 -B`, stdin
`/dev/null`, and the packet94 serial compiler lock. Run `build_engine.py`,
`bracket_config.py`, `full_shape.py`, `reset_gate.py`, `protocol_gate.py`,
`startup116.py`, `limit_gate.py`, `launch_limit_gate.py`, `test_policy.py`,
`cpu_seal.py --operator-evidence PATH`, then `queue_plan.py`. The source-copy
scripts are historical derivations; committed sources are the build inputs.
The queue planner only writes the new proposed file and a temporary queue.
