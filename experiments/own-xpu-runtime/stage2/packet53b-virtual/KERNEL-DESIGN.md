# Exact-order logical lanes

Each physical lane holds V consecutive original logical lanes. Every logical
chain visits begin + 256*t + 8*logical_lane and its eight products in order.
It retains a separate FP32 sum. The first log2(V) adjacent reduction levels
execute within that lane; the remaining levels use subgroup shuffles over
32/V physical lanes. Each subgroup therefore processes V adjacent rows.
This is the same tree, with a different assignment of work.

Experts retain compact production pitches,
route/status/error handling and global IQ2 table. Paired V4 retains packet53's shared input load and 8V rows per 256-thread
workgroup. V8/V16 gate/up instead use two subgroups per set of V rows, one
for gate and one for up, hence 4V rows per workgroup. This is the registered
spill-free replacement: only V sums live per lane. The shared input is loaded
once per stream; that extra load is included in timing. Down uses 8V rows. Down checks k<K separately for every chain.

HC low uses four subgroups per 128-thread workgroup, one per original split,
for V rows. The 4V local floats preserve all four row partials. Every lane,
including padded rows, reaches the barrier. The final sum is (p0+p1)+(p2+p3),
followed by original BF16 storage and silu/div4 epilogue. Gate uses four
subgroups × V rows without a split. Its K320 tail is checked per chain.
Both sides keep low → activation → gate order, four compute events total.

Small FFN uses one 128-thread tuple launch: F32 router512, Q6 gate640,
Q6 up640 and F32 scalar shared gate1, all K2560 and Split4. Each workgroup
selects one member uniformly, including the scalar's padded rows.
No tuple member is timed separately or omitted.

The CPU proof compares candidate chains to original expanded/kopt2 lane
implementations and an independent scalar expert decoder. Adversarial trees
reject reassociation. Whole operators check invalid routes, partial rows,
active/sticky controls and HC position guards. The full fixture uses real
production dimensions, ten distinct routes, complete output/state captures
and independent production CPU expected bytes, including HC dependencies.
The device windows repeat all M1/M2 cases against actual device controls.

Packet49c uses four-byte row alignment: IQ2 K2560 pitch820, IQ4 K640 pitch360.
Packet53's original fixture used 832/368. Both packet53b controls and candidates
use the exact packet49c bytes via `production_gemv.hpp`; `check_controls.py`
compares the full layout/decoder with packet49c and the control bodies after
only namespace and binding-offset normalization. Packet53 measurements retain
their own original identity; none are borrowed as packet53b timing controls.
