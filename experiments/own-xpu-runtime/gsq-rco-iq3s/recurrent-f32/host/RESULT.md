# Corrected recurrent Host lifecycle

The root-operated synthetic Host run passed; independent closed readback is `evidence/independent-actual-review.json` (fb961306acb5045cf37cbee98ce3714175755ccb4371727a43c73c359a99b5dd). It verified129 retained files/879,203B, including all6 target bundles, without rerunning the proof.

One pair of Host owners executed initial RESET, target-only4 outputs, RESET, and MTP4 outputs. Confirmed tokens and complete corrected target state matched. Three guesses produced two hits and one miss, exercising one actual snapshot restore/redo. The explicit final DUMP repeat and closed readback matched; both owners exited safely with no live allocations, in-flight events, retained children, or signals.

The actual dumps contain24 F32 recurrent ranges with correct192/240/2304-byte mini extents and288 words that would lose bits if stored as BF16. Initial recurrent ranges were zero. All24 checked attention ranges retain BF16 extents. This confirms the changed storage through actual mini Engine allocation, typed tiny dispatch, snapshot/rollback, RESET, and bundle capture. The focused522-check HostTeam proof separately covers the production GDN geometry.

This uses synthetic tiny weights and CPU Host owners. It does not establish native-device F32 behavior, same-weight reference equivalence, or broad quality. The next bounded native pair requires its own physical ownership, allocation census and new F32 target/MTP oracle; old BF16 state hashes are not an acceptance target.
