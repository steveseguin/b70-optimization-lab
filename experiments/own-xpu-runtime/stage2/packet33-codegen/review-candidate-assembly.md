# Independent candidate assembly review


Independent inspection found another source-to-GEN surprise. `down.bank`
eliminates all table gathers, but the second full tile uses eight separate u16
BF16 input gathers rather than four packed d32 gathers. Its finite normal-scale
interior path is231 GEN instructions and11 data messages per eight weights
(one scale u16, two code d32, eight input u16). The first tile has four packed
input loads and7 messages. This is not uniform across the unrolled bodies.

`down.select` also removes table loads, but the compiler introduces divergent
branches for each nested integer selection. It retains eight byte-code loads
and eight u16 input loads plus scale:17 messages per eight weights. Its
interior tile CFG sum is269–285 for a single homogeneous lookup branch path,
and461 for the union when all lookup branch arms have active SIMD lanes.
These conditional CFG sums are not measured instruction issue counts. The
source notation as nested selects did not guarantee branch-free GEN.

These first candidate dumps were sent back for source iteration, specifically
to preserve packed BF16 input loads for the bank approach. Hash-bound initial
review rows remain in JSON even if a later iteration supersedes them.

## Iteration1 recheck

The new hash-bound bank dump reaches the intended memory-message change.
All three unrolled tiles now contain one u16 scale gather, two packed d32
code gathers and four packed d32 BF16 input gathers:7 messages per eight
weights, with zero table gathers. The normal finite interior CFG path is
188 GEN instructions (B022,B023,B024,B031), versus231 for the initial bank
and169 for p29 WG32. Whole static instructions fall from965 to843.

Relative to p29 this exchanges eight fewer sends for nineteen extra GEN
instructions per interior tile. It retains SIMD32 and A64 pointer additions;
no new barrier or scratch traffic appeared. The assembly verifies the intended
change, but only a future matched device timing can decide the trade.

The final module also recompiled the unchanged select source. Its register
allocation/scheduling differs:1757 whole static instructions, interior
lookup-path CFG sums290–306 homogeneous or482 for the mixed-arm union,
with the same17 messages per eight weights. The initial1703/461 counts
above are retained only as iteration0 history, not final binary counts.
