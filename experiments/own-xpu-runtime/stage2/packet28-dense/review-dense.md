# Independent dense arithmetic review

Reviewer read packet28 `dense.hpp`, packet10 `expanded.hpp` (`value`, `lane`, `row`, `expand`) and packet2 `math.hpp` (`decode`, `element`, output rounding). This review was performed independently of the dense implementation author.

No finite-value arithmetic defect found. For Q6/Q8, the scale byte offset `K + 4*(i/group)` exactly matches expanded code size plus scale index, where groups are 16/32. Scale byte assembly and signed-code conversion match current. Every active production tile begins at `256*t + 8*lane`, a multiple of eight; an eight-weight segment cannot cross a 16/32-weight group boundary. The explicit segment loop additionally handles nonaligned ranges without borrowing the next scale. The upgraded Q8 layer chooses 32-weight groups through the type specialization.

Exceptional Q6/Q8 scales call unchanged `expanded::value` per weight. This preserves the current expression, including 0*infinity and NaN handling. Raw F32/F16/BF16 paths use unchanged scalar `decode`; BF16 NaN quieting is preserved. Candidate value*input then sum+product retains the exact per-lane order; the row helper uses unchanged adjacent SG32 and split4 trees. Production BF16 rounding remains in the enclosing submission code, not moved into a lane or tile.

Counts correction communicated to the root: packet10's explicit exceptional-scale predicate applies only to IQ2/IQ3, not expanded Q6/Q8. For a fully specialized old Q6/Q8 kernel, that branch is dead; a README must not promise removal of eight live NaN checks without generated-code evidence. New Q6/Q8 code adds one exceptional predicate per tile while reducing scale byte assembly/addressing from eight to one.

Known limitation: strict finite arithmetic flags do not define which NaN operand payload wins when multiple NaNs are added/multiplied. Host fixtures must report current/new encoding differences separately, and G2 must reject a candidate whose bytes differ from current on the same card. Independent review cannot substitute for that pending same-card gate.
