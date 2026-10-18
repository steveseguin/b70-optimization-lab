# Packet104 selected-operation access census

Baseline is packet100 `down-tile16`, with selection and dispatch snapshots
in this directory. Optional kernels are not timing controls. The copied
sources and exact originals are identified by `source-origin.json`.

| Stream | Selected operation / pattern | Decision |
| --- | --- | --- |
| Target down IQ4 | `p100::Kernel<2>`; 16 rows per subgroup | Keep accepted down-tile16 in every runtime view. |
| Target gate/up IQ2 | p65 wide64, eight rows per subgroup | Micro normal half scales and separate exact float-half-cache arm; four independent planes. |
| Draft routed INT8 gate/up/down | mtp36 WG128, one row per subgroup | Requested boundary measurements against actual selected kernels; do not substitute optional p59 multirow. |
| Draft shared BF16 gate/up | mtp36 WG128, one row per subgroup, unfused activation | Requested boundary measurement; same operation applies independently to both weights. |
| Draft shared BF16 down | p33 WG32, one row per subgroup | Requested boundary measurement. |
| Target HC Q8 gate/up | p73 two rows per subgroup, fused four-stream mix | Micro full operation; conversion dependency remains. |
| Target shared Q6 gate/up | p49d small tuple, four rows per subgroup, Split4 | Micro full selected tuple with only these two banks transposed. |
| Target F32 expert router | Same small tuple, four rows per subgroup, Split4 | Separate full-tuple micro with only router transposed. |
| Target F32 scalar shared router | Same tuple, one output row | Keep unchanged; no full 16-row tile. |
| Target shared Q8 down | Dispatch `p33.dense.segment`, WG32, one row per subgroup | No matching within-subgroup multirow pattern. |
| GDN qkv/z, QSA qgate | p33, one row per subgroup | Do not open attention arm. |
| QSA k/v | p28 rows4 means four rows across four subgroups | No within-subgroup row match. |
| Attention output | p49c Q6 Split4, one row/part per subgroup, separate combine | No matching pattern. |

Packet100 packs same-column chunks from 16 adjacent rows together, reducing
the distance between the row loads issued by a subgroup. Better transaction
locality, DRAM page locality and L3 reuse are plausible mechanisms. Timing
does not distinguish those mechanisms; no page-hit/L3 counter claim is made.

IQ2 still performs dependent grid lookups. HC still converts Q8 values. The
new layout changes only byte addresses; any speed benefit must pass the
preregistered measured gate. The full tuple comparison includes the unchanged
sibling work, so a router-only or shared-only gain cannot hide tuple overhead.

The negative records for packets 65/73/74/81/90/95/99/102 close other geometry,
packing, conversion-cache, table, prefetch or batching changes. In particular,
packet74's packed-source dense experiment excluded the fused small-FFN tuple.
Preserving expanded bytes and metadata in tile16 does not reopen that arm.
