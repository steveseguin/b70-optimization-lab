# Small dense kernels

All estimates below are hypotheses for G3, not measurements. Arithmetic identity stays `iq3-p17-detmath-v2`.

| Class | Incumbent work and cost | Candidate | Hypothesis, us/group |
|---|---|---|---:|
| hc.a.gate / hc.f.gate | 10240 rows x 320 Q8 columns, SG32 tree. Packet 28 selected wg32; historical expanded runtime cost about 30 us includes 10240 independent row groups and two 256-column tiles. | SG32 and four independent SG rows/WG; same p28 arithmetic. | 18–28 |
| small.hc | packet27 merged low 320 x 10240 split4 + inject 4 x 10240 split4: 324 WG x 128 WI, one barrier per WG, four-float SLM, about 18.5 us. | One SG per row computes its four original split partials sequentially, then `(p0+p1)+(p2+p3)` in lane 0. One tuple launch, 324 WG32 or 81 WG128. | 12–24 |
| small.ffn.q6 | Router 512 rows, shared gate 1 row, two 640-row projections; 1793 WG128, split4 barrier per WG. About 31 us for the tuple. | Compile-time tuple, 1793 SG32; SG32 or rows4 placement, no SLM/barrier. | 20–40 |
| small.ffn.q8 | Same rows; gates are split1, four rows/WG, giving 833 WG128; router/shared split4. | 1793 SG32, with original split1 versus split4 per member retained. | 20–40 |
| shexpdown | 2560 x 640 Q8, three 256-column tiles. Packet28 wg32 is the incumbent; historical runtime about 16 us. | SG32 or four independent rows/WG. | 10–18 |

The fixed launch overhead provided by the card measurements is 3.4–5 us. The fixed cost specific to each shape is not separately measured: a whole-kernel time cannot be honestly labeled launch overhead. In every full production row, all 32 lanes perform at least one nonempty eight-product sequence. Gate K=320 has 24 lanes without work in its last tile; down K=640 has 16 lanes without work in its last tile. These lanes still perform work in earlier tiles. In rows4 placement the 1793-row FFN tuple has three padded subgroups (96 WI) in its final WG; SG32 has none. No full production WG is empty. Reduction nodes deliberately become inactive as their original tree combines: this is necessary arithmetic, not an avoidable missing row.

Packet28's gate/down winners are already barrier-free; these alternatives may tie or lose. The larger mechanism is removing split4 WG rendezvous from the two existing merged tuples. Serializing splits inside an SG can also lose parallelism; G3 must decide.

The gate is **not** merged with low/inject. Low/inject consume 10240 stream elements. Gate consumes the 320-element BF16 activation produced after low. Combining independent WG domains across this dependency would be a race. The valid merged siblings remain low+inject and router+shared gate/up+shared scalar gate, using compile-time member types without a device interpreter.

Each lane executes the original ordered sequence `sum = sum + (weight * input)`, with no contraction. Five adjacent SG shuffle levels reproduce `tree32`. Split4 retains all four original tile boundaries and the exact final two-level partial tree. BF16 conversion occurs once at the original output boundary. `small_cpu.cpp` compares all production rows against expanded incumbent arithmetic and a separate packed-byte equation; F32 lengths 1, 3, 33, 257 cover short and odd tails, and the shared scalar output covers a one-row matrix.

`small.hpp` exposes reusable `Fixture`, `shapes`, `Bound`, `validate`, and CPU evaluation. The `submit` entry validates extents/aliases and returns a single event. Host allocation padding never changes a row stride. Incumbents for hc.gate/shexpdown must call packet28 `p28::submit(...,p28.dense.wg32,...)`; small tuples call packet27 `small::submit`. Individual hc.a.low's packet28 rows4 winner is for an unfused allocation path and is not a replacement baseline for the already merged `small.hc` tuple.
