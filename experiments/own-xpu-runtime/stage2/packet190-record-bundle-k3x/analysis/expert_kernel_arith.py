#!/usr/bin/env python3
"""Arithmetic behind expert-kernel-study-20261023.md (CPU-only, no device, no repo edits).

Every input below is a number read from the ledger; the file path it came from is in
the comment next to it. Run: nice -n 19 python3 -B expert_kernel_arith.py
"""
# ---- shapes (packet103-record-bundle/p49d_expert_submit.cpp, p90_layout.hpp, p100_down.hpp) ----
HIDDEN = 2560           # K of gate/up rows
INTER = 640             # rows per expert for gate/up; K of down
EXPERTS_ROUTED = 10     # count=10 slots per token
EXPERTS = 512
LAYERS = 48             # 36 GDN + 12 QSA (k2-class-registry groups_per_token)
IQ2S_BLOCK_BYTES = 82   # GGUF IQ2_S: 2 d + 64 qs + 8 qh + 8 scales per 256 weights (p49bgemv::layout)
ROW_GATE_PACKED = 820   # p49bgemv::layout(IQ2_S,2560).row_bytes
ROW_GATE_E1 = 840       # p90::expert_stride: FP16 d replaced by FP32 (10 blocks x 4 B)
ROW_DOWN = 360          # IQ4_NL 20 blocks x 18 B (p100::row_bytes)

gate_rows = EXPERTS_ROUTED * INTER                       # 6400 rows per stream
gate_bytes_packed = 2 * gate_rows * ROW_GATE_PACKED      # gate+up, GGUF-packed bytes
gate_bytes_runtime = 2 * gate_rows * ROW_GATE_E1         # what the record kernel reads
down_rows = EXPERTS_ROUTED * HIDDEN                      # 25600 rows
down_bytes = down_rows * ROW_DOWN
gate_weights = 2 * gate_rows * HIDDEN                    # 32,768,000
down_weights = down_rows * INTER                         # 16,384,000
act_x = HIDDEN * 2; down_x = EXPERTS_ROUTED * INTER * 2  # activations (BF16)

# ---- device (packet7-kopt2/analysis.json: max_compute_units 256; notes xpu-smi 2800 MHz; packet119 L2 25,165,824 B) ----
XVE = 256; CLOCK = 2.8e9; THREADS_PER_XVE = 8; L2 = 25_165_824
SLOTS = XVE * THREADS_PER_XVE                            # 2048 resident SIMD32 subgroups

# ---- measured (us per call, one rank, the layer runs on exactly one rank) ----
meas = {
 'packet110 roofline.json expsgate (p90 E1 halfcache, WG64, GDN@128)': 60.365,
 'packet110 roofline.json expsdown (wide64 virtual16 planar, pre-tile16)': 50.886,
 'packet77 raw events rank0 gate/down (packet81 ANALYSIS.md)': (61.54, 52.19),
 'packet86 production rank1 ms/half /24 gate, down (verdict note)': (1.495e3/24, 1.208e3/24),
 'packet100 tile16 down micro ratio (real routes)': 0.695,
 'packet162b production gate/up, 10-expert bank, L2-resident (analysis.json)': 48.33,
 'packet191 sampled class experts incl. act, +~32us/layer recorder spread (note)': 105.0,
 'packet110 expsact': 5.417,
 'packet86 exp-nodeq gate (loads kept, decode removed) ms/half/24': 0.811e3/24,
 'packet86 exp-constgrid gate ms/half/24': 0.923e3/24,
 'packet86 exp-loadkeep gate ms/half/24': 1.573e3/24,
 'packet86 exp-onecached down ms/half/24': 0.849e3/24,
}
copy_bw = (537e9, 555e9)

def us(b, bw): return b / bw * 1e6

print('== A. bytes per layer per token ==')
print(f'gate+up rows {gate_rows} x2 streams; packed {gate_bytes_packed:,} B; runtime (E1 840-B rows) {gate_bytes_runtime:,} B; weights {gate_weights:,}')
print(f'down rows {down_rows}; bytes {down_bytes:,} B; weights {down_weights:,}')
tot_runtime = gate_bytes_runtime + down_bytes + act_x + down_x + 2*gate_rows*2 + down_rows*2
print(f'total runtime read+write incl. activations/outputs ~ {tot_runtime:,} B')
for bw in copy_bw:
    print(f'  copy floor @{bw/1e9:.0f} GB/s: gate/up {us(gate_bytes_runtime+act_x+2*gate_rows*2,bw):.2f} us, down {us(down_bytes+down_x+down_rows*2,bw):.2f} us, class {us(tot_runtime,bw):.2f} us')
print('  packet110 floors (their byte formulas): expsgate 20.08, expsdown 17.28, sum 37.36 us; packet191 analysis.json experts excess 79.7 over floor 36.96')
print('  NOTE: lever synthesis 4 says "111 us (excess ... 74 us)"; the brief misquotes 74 as the FLOOR. Floor is 37.4; excess is 74.')

print('\n== A. measured ==')
for k, v in meas.items(): print(f'  {k}: {v if not isinstance(v,float) else round(v,2)}')
gate_engine = 60.4; down_engine_tile16 = 50.9*0.695  # best available estimate of the record down kernel
print(f'  record-line estimate per layer: gate/up {gate_engine:.1f} + down(tile16) ~{down_engine_tile16:.1f} + act 5.4 = {gate_engine+down_engine_tile16+5.4:.1f} us (packet191 sampled 105 incl. recorder share)')
print(f'  excess over copy floor: {gate_engine+down_engine_tile16+5.4-37.36:.1f} us/layer; gate/up alone {gate_engine-20.08:.1f}; L2-warm gate/up still {48.33-20.08:.1f} over floor')

print('\n== A. occupancy / grid (p90 Kernel<IQ2_S,2560,WG64,false,true>; p100 Kernel<2>) ==')
V_gate, P_gate = 8, 4; sg_gate = 2*gate_rows//V_gate; wg_gate = sg_gate//2
V_down, P_down = 16, 2; sg_down = down_rows//V_down; wg_down = sg_down//2
print(f'  gate/up: WG64 = gate SG32 + up SG32, V={V_gate} rows/SG, P={P_gate} lanes/row -> {wg_gate} WGs, {sg_gate} SGs = {sg_gate/SLOTS:.0%} of {SLOTS} slots (one wave, {sg_gate/XVE:.2f} SG/XVE)')
print(f'  down:    WG64 = 2 SG32, V={V_down}, P={P_down} -> {wg_down} WGs, {sg_down} SGs = {sg_down/SLOTS:.0%} (one wave)')
print(f'  per gate lane: 8 chains x 10 steps = 80 tiles of 8 weights; loads per step per lane: 1 d32x4 codes + 2 d16 (high,scales) + 1 d32 (FP32 d) + 8 d32x2 grid + 32 d32 inputs (packet81)')

print('\n== A. instruction budget (issue-bound model: 256 XVE, SIMD32 instr = 2 clk on a SIMD16 datapath) ==')
def issue_us(weights, instr_per_weight, clk_per_instr=2.0):
    return weights/32*instr_per_weight/XVE*clk_per_instr/CLOCK*1e6
for name, w, static_pw in (('gate/up', gate_weights, 21.92), ('down', down_weights, 19.5)):
    dyn = {'gate/up':16.0,'down':15.0}[name]   # normal path (exceptional path excluded) from the opcode histogram
    print(f'  {name}: static {static_pw}/weight (incl. exceptional path), normal-path dynamic ~{dyn}/weight -> issue time {issue_us(w,dyn,1):.1f} us @1clk, {issue_us(w,dyn,2):.1f} us @2clk')
    floor = 20.08 if name=='gate/up' else 17.28
    budget = floor*1e-6*CLOCK*XVE/(w/32)
    print(f'     copy-floor budget = {budget:.1f} XVE-cycles per 32 weights = {budget/2:.1f} SIMD32 instr/weight @2clk; exact-identity minimum ~9-10 instr/weight -> ALU floor {issue_us(w,9.5,2):.1f} us')
print('  => gate/up L2-warm 48.3 us ~= issue time at ~16 instr/weight x 2 clk (46 us): issue/dependency-bound, not DRAM-bound.')

print('\n== C. bars ==')
two_card_bar = 15.1; one_card_bar = 11.4
print(f'  two cards: +2% needs {two_card_bar} us/layer on both ranks (+1.32% per 10 us); one card: {one_card_bar} us/layer on all 48 (0.545 ms/token)')
ceil = {'act epilogue via SLM in WG64 (exact)': (4,5), 'register-free LSC prefetch (gate/up engine - L2warm; down unknown)': (0,12), 'instruction diet gate/up 16->12/weight': (0,12), 'instruction diet down 15->11/weight': (0,7)}
lo = sum(v[0] for v in ceil.values()); hi = sum(v[1] for v in ceil.values())
for k, v in ceil.items(): print(f'  {k}: {v[0]}-{v[1]} us/layer')
print(f'  sum of ceilings {lo}-{hi} us/layer at 100% transfer; ledger transfer for this class 0% (p104b), 47-100% (p100)')
