# Packet67: roofline audit and three non-expert candidates

The byte audit and CPU preparation are complete. No GPU or CPU model was run. Packet64, packet61x, packet65, packet66, existing screen trees and ops trees were not changed by this work. The existing 51.03 tok/s record is unchanged; device quality and speed for packet67 remain pending.

The [roofline table](../experiments/own-xpu-runtime/stage2/packet67-roofline/ROOFLINE.md) was committed and pushed first as `bf231e314`. It reads all three actual GGUF headers, checks 1,224 tensors against the admitted census, and accounts for expanded runtime Q6/Q8 storage. Every sampled non-speculative per-layer call is represented on both ranks; all 48 layers have separate byte inventories. Multiple kernel events belonging to one call are summed before taking medians. This makes attention about 46 µs, route about 19 µs and QSA attention about 44 µs. The brief's event medians understated these complete calls.

After the packet65-owned experts, the largest rank0 excesses over a 540 GB/s useful-byte floor are recurrence (539 µs/half), route (464), FFN HC gate (434), and attention HC gate (433). QKV/Z/Q-gate are already near 500–511 useful GB/s. These are byte-model excesses, not achievable gains or measured physical DRAM traffic. Individual outside-layer timings are absent; the table gives their bytes and floors without inventing bandwidth. The full target head differs from the shorter draft head. Draft activation/state traffic is explicitly incomplete.

The selected sites are recurrence and both HC gates. The HC candidate groups four streams into one subgroup and preserves each output's reduction tree, BF16 rounding and stream sum order. The recurrence candidate calculates shared head normalization/decay/beta once, then runs the unchanged state arithmetic. It adds one kernel and uses 49,920 bytes of existing scratch; rollback includes the new scratch range. Route is deferred for a separate study of its existing packet54 changes.

The initial virtual HC reduction failed NaN payload identity. The exact rejected source and evidence are retained; the final version uses the original arithmetic for exceptional inputs. Both GNU and Intel now pass 60 cases twice each, with no tolerance. Actual submission interfaces, invalid bindings and 15 selection-parser cases also pass. Offline compilation of the actual translation units passes, but HC flag pressure remains a risk. Device execution is still needed to establish parity and useful speed.

Five views share one binary: production, hc-a, hc-f, rec-head and combined. Planning budgets are 87, 87 and 108 µs/half (combined 281 before rounding), simply 20% of the audit's memory excess; they are not measured or promised gains. [Preparation closeout and evidence](../experiments/own-xpu-runtime/stage2/packet67-roofline/CPU-PREPARATION-CLOSEOUT.md).

The coordinator's next step is the [sealed quick lane A/B jobs](../experiments/own-xpu-runtime/stage2/packet67-roofline/WINDOW.md): production first/last, each candidate once, reversed candidate order between lanes, a 3,600-second watchdog and no retry. The compare helper checks packet49 tokens and reports each lane against its own controls. These 128-token screens are diagnostic; they cannot promote a speed record. The packet49 oracle remains the authority.

## Device result and closeout (coordinator, 2026-10-17 20:10 UTC)

Lane-B quick screens, 18:58–19:28 UTC: every candidate was exact 13/13 and **slower** than same-lane production control (52.17 tok/s).

| Candidate | Change |
|---|---|
| `combined` | −21.8% |
| `rec-head` | −11.8% |
| `hc-f` | −6.3% |
| `hc-a` | −7.0% |

The sixth screen (`p67-quick-B-6-production-a`) finished its suite. Its teardown was then refused by the packet 70 K2 window's undrained record; the coordinator recovered it cooperatively at 20:09. See `ops/review-log.md`, review 7.

The lane-A copy was stopped by rule: `screen/evidence/STOP` was written by `fn-run/p67-stop-rule.sh`, because no lane-B candidate reached ≥ +1.5%.

**Closed: no promotion.** Lesson: candidates picked by useful-byte roofline excess, without in-engine achieved-bandwidth evidence, went 0 for 4. Packet 72 picks classes by measured in-engine GB/s and applies packet 65's `wide64` occupancy approach instead.
