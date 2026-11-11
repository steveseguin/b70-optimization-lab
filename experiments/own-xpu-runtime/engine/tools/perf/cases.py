"""Calibration cases for predict.py: kernel machine code + launch shape + bytes + measured GPU time per launch.

Each case: id, group, dump (directory of IGC .asm dumps), match (regex on isa_census.py's short name) or parts
(several thread kinds in one launch: [{dump, match, threads, trips, skip}]), wg (work-group items), groups
(work-groups), threads (active sub-groups; default all), bytes (read per launch), cold (weights from DRAM; False =
a bench repeating one launch, data in L2), loads ("warm": global loads wait the L2 latency even in a cold
launch: activations the previous launch wrote; default "cold" when cold), hot (regex on the load text: loads that
hit cache, lat_gl_hot; set automatically for the quantized row kernels' activation loads), trips_bytes ((load regex,
bytes per sub-group): the trips of a kernel's one loop from the bytes it must load, for the dense forms whose K loop
the compiler did not fully unroll), trips ({loop id: trips}, loop ids from isa_census.py), skip (blocks of
a runtime branch this launch does not take), us (measured, median per launch), fit (False = shown, not fitted:
data-dependent loops whose trips are not known), per_step (engine cases: launches of this kind per answer step on
card 2, same profile), src (where the measurement is).

Dumps (made on the host, no GPU: tools/perf/dump_isa.sh):
  isa-engine82   tools/perf/engine_kernels_tu.cpp against /home/steve/dsv41-work/src82 (the profiled g82 build)
  isa-dense_m16  tools/bench/bench_dense_m16.cpp   isa-norm_ff     tools/bench/bench_norm_ff.cpp
  isa-route_rows tools/bench/bench_route_rows.cpp  isa-route_pick  tools/bench/bench_route_pick.cpp
Bench sources are the current files; the measured runs (round18 n5, rt5, rp r3, d3, d4) used the same forms.
"""
import re

P = "/home/steve/dsv41-work/perf/"
ENG, DEN, NRM, RTR, RPK = P + "isa-engine82", P + "isa-dense_m16", P + "isa-norm_ff", P + "isa-route_rows", P + "isa-route_pick"
DATA = "data/dsv41-bringup-20261109/"


def ex(name):
    return "^" + re.escape(name) + "$"


CASES = []


# Quantized row kernels (GemvQ8P / GemvQ6KP / GemvQ5KP / Q8V / Routed*) load the activations as 256-byte block loads
# (load.ugm.d32x64t) and the weights as d32x32t / d16u32 / d8u32: the activations are re-read by every work-group
# and hit cache, so their latency is lat_gl_hot, not the DRAM latency. (GemvH16P loads weights and activations
# with the same d32x64t form, so it gets no hot pattern.)
ACT = r"load\.ugm\.d32x64t"
QROWS = re.compile(r"GemvQ|Q8V<|Routed")


def _hot(d, match):
    if "hot" not in d and match and QROWS.search(match):
        d["hot"] = ACT


def add(**c):
    c.setdefault("cold", True)
    c.setdefault("wg", 512)
    _hot(c, c.get("match"))
    for pt in c.get("parts") or []:
        _hot(pt, pt["match"])
    CASES.append(c)


# ---------------------------------------------------------------- engine decode, card 2 (round18 g82 profile)
G82 = DATA + "round18-g82-pf_new-decode-profile-card2.txt"
# loads="warm": the launch reads activations the previous launch wrote (L2-resident), not streamed weights
HCF = {"dump": RTR, "match": ex("RowsP<HcFinishRows>"), "threads": 1, "trips": {0: 8, 1: 8, 2: 20}, "loads": "warm"}
for name, groups, mb, us, what, per_step in [
        ("GemvQ8P<128u, ActF32> @wg512", 128, 8.91, 18.06, "o_a Q8_0 2048x4096", 27),
        ("GemvQ8P<256u, ActF32> @wg512", 54, 7.52, 16.14, "o_b Q8_0 864x8192", 27),
        ("GemvQ8P<72u, ActF32> @wg512", 54, 2.12, 6.30, "shared down Q8_0 864x2304", 27),
        ("GemvQ6KP<16u, ActF32> @wg512", 128, 6.88, 19.56, "o_a Q6_K", 13),
        ("GemvQ6KP<32u, ActF32> @wg512", 54, 5.81, 15.04, "o_b Q6_K", 13),
        ("GemvQ6KP<20u, ActF32> @wg512", 1347, 90.69, 158.97, "output head Q6_K 21552x5120", 1),
        ("GemvQ6KP<24u, ActF32> @wg512", 267, 21.53, 45.91, "engram_kv Q6_K 4272x6144", 2),
        ("GemvQ5KP<9u, ActF32> @wg512", 54, 1.37, 6.31, "shared down Q5_K", 13),
        ("GemvH16P<160u, ActF32> @wg512", 25, 4.13, 9.22, "router / compressor rows (halves)", 47),
        ("GemvH16P<16u, ActF32> @wg512", 8, 0.131, 2.91, "publish: indexer k", 2),
        ("RowsP<RowsPair<NoRows, RowsPair<DenseRows<GemvQ8P<160u, ActF32> >, DenseRows<GemvQ8P<160u, ActF32> > > > > @wg512",
         112, 9.75, 19.68, "q_a + kv Q8_0 1792x5120", 24),
        ("RowsP<RowsPair<NoRows, RowsPair<DenseRows<GemvQ6KP<20u, ActF32> >, DenseRows<GemvQ6KP<20u, ActF32> > > > > @wg512",
         112, 7.54, 17.46, "q_a + kv Q6_K", 13)]:
    add(id="eng " + what, group="engine dense", dump=ENG, match=ex(name), groups=groups, bytes=mb * 1e6, us=us,
        per_step=per_step, src=G82)
# fused launches: a serial row (the stream-mix finish) beside the dense rows
add(id="eng q_b Q8_0 8192x1280 + mix finish", group="engine fused", wg=512, groups=513, bytes=11.14e6, us=23.41, per_step=27,
    parts=[{"dump": ENG, "match": ex("GemvQ8P<40u, ActF32> @wg512"), "threads": 8192}, HCF], src=G82)
add(id="eng q_b Q6_K + mix finish", group="engine fused", wg=512, groups=513, bytes=8.65e6, us=21.60, per_step=13,
    parts=[{"dump": ENG, "match": ex("GemvQ6KP<5u, ActF32> @wg512"), "threads": 8192}, HCF], src=G82)
add(id="eng q_a+kv Q8_0 + attn dots (L0/1/14)", group="engine fused", wg=512, groups=125, bytes=11.72e6, us=23.66, per_step=3,
    parts=[{"dump": ENG, "match": ex("GemvQ8P<160u, ActF32> @wg512"), "threads": 1792},
           {"dump": NRM, "match": ex("RowsP<HcDotsRows<5120u, 8u> > @wg512"), "threads": 200}], src=G82)
add(id="eng norm + mix dots @wg64 (ff)", group="engine fused", wg=64, groups=102, bytes=2.07e6, us=8.25, per_step=77,
    parts=[{"dump": NRM, "match": ex("RowsP<NormRows<5120u, 4u> > @wg512"), "threads": 4,
            "skip": "B020-B032,B043-B072", "loads": "warm"},
           {"dump": NRM, "match": ex("RowsP<HcDotsRows<5120u, 8u> > @wg64"), "threads": 200}], src=G82)
# routed experts: L0 = grid table into local memory (TAB / 512 trips), L1 = rows per sub-group (2048 sub-groups)
for name, tab, rows, mb, us, per_step in [("RoutedIQ2SP<20u, ActF32, NoRows>", 8192, 4608, 7.59, 51.14, 15),
                                          ("RoutedIQ2XXSP<20u, ActF32, NoRows>", 2048, 4608, 6.49, 34.84, 15),
                                          ("RoutedIQ1SP<20u, ActF32, true, NoRows>", 4096, 4608, 4.64, 52.08, 10),
                                          ("RoutedIQ2SP<9u, ActF32, NoRows>", 8192, 5184, 3.90, 27.99, 15),
                                          ("RoutedIQ3XXSP<9u, ActF32, NoRows>", 1024, 5184, 4.64, 25.22, 15),
                                          ("RoutedIQ2XSP<9u, ActF32, NoRows>", 4096, 5184, 3.48, 25.11, 6),
                                          ("RoutedIQ2XXSP<9u, ActF32, NoRows>", 2048, 5184, 3.32, 20.60, 3)]:
    add(id="eng experts " + name.split(",")[0], group="engine experts", dump=ENG, match=ex(name + " @wg512"),
        groups=128, bytes=mb * 1e6, trips={0: tab / 512, 1: rows / 2048}, us=us, per_step=per_step, src=G82)
# attention, n_idx ~ 190 (positions 36-83 of a 4K run: 160-224 slots)
add(id="eng SparseScoreHG<512,4>", group="engine attention", loads="warm", dump=ENG, match=ex("SparseScoreHG<512u, 4u> @wg32"),
    wg=32, groups=24, trips={0: 16}, bytes=0.22e6, us=8.46, per_step=38, src=G82)
add(id="eng SparseSoftmaxPN<640>", group="engine attention", loads="warm", dump=ENG, match=ex("SparseSoftmaxPN<640> @wg32"),
    wg=32, groups=16, bytes=0.03e6, us=5.79, per_step=38, src=G82)
add(id="eng SparseOutJC<512,16,128>", group="engine attention", loads="warm", dump=ENG,
    match=ex("SparseOutJC<512u, 16u, 128u, 16u> @wg512"), wg=512, groups=16, trips={0: 2}, bytes=0.21e6, us=5.61, per_step=40,
    src=G82)
# serial and small launches
add(id="eng EngramGateP (3 double chains)", group="engine serial", loads="warm", dump=ENG, match=ex("EngramGateP @wg32"), wg=32,
    groups=4, trips={0: 160, 1: 160}, bytes=0.26e6, us=116.07, per_step=2, src=G82)
add(id="eng HcPostPreP", group="engine small", loads="warm", dump=ENG, match=ex("HcPostPreP<ActF32> @wg64"), wg=64, groups=80,
    bytes=0.2e6, us=1.24, per_step=78, src=G82)
add(id="eng WindowAppendP", group="engine small", loads="warm", dump=ENG, match=ex("WindowAppendP<ActF32> @wg64"), wg=64, groups=8,
    bytes=0.005e6, us=2.14, per_step=40, src=G82)
add(id="eng SwigluBothS", group="engine small", loads="warm", dump=ENG, match=ex("SwigluBothS<ActF32> @wg64"), wg=64, groups=42,
    bytes=0.03e6, us=1.10, per_step=40, src=G82)
add(id="eng MoeCombineA", group="engine small", loads="warm", dump=ENG, match=ex("MoeCombineA<ActF32> @wg32"), wg=32, groups=27,
    trips={0: 6}, bytes=0.03e6, us=1.48, per_step=40, src=G82)
add(id="eng RowsP<RopeRows>", group="engine small", loads="warm", dump=ENG, match=ex("RowsP<RopeRows<ActF32> > @wg512"), groups=1,
    threads=1, bytes=0.002e6, us=0.92, per_step=40, src=G82)
# not fitted: the router pick inside (data-dependent loops), the 1280/512 norms (both paths compiled)
add(id="eng router + finish + shared Q8_0 (two-stage pick)", group="engine fused", wg=512, groups=50, bytes=4.18e6,
    us=12.83, fit=False, per_step=27, src=G82,
    parts=[{"dump": RTR, "match": ex("RoutePRows<NoRows>"), "threads": 16, "loads": "warm"},
           HCF, {"dump": ENG, "match": ex("GemvQ8P<160u, ActF32> @wg512"), "threads": 768}])
add(id="eng norms 1280 + 512 @wg64", group="engine fused", loads="warm", dump=ENG, wg=64, groups=3, threads=6, bytes=0.007e6,
    match=ex("RowsP<RowsPair<NormRows<1280u, 4u>, NormRows<512u, 2u> > > @wg64"), us=4.10, fit=False, per_step=40,
    src=G82)

# ---------------------------------------------------------------- norm bench (round18 n5, warm, back to back)
N5 = DATA + "round18-n5-norm-ff-bench.txt"
NR = ex("RowsP<NormRows<5120u, 4u> > @wg512")
CHAIN, FAST = "B003-B019,B043-B072", "B020-B032,B043-B072"   # NormRows: ff path B003-B019, chain B020-B032
DOTS = lambda wg: {"dump": NRM, "match": ex(f"RowsP<HcDotsRows<5120u, 8u> > @wg{wg}"), "threads": 200}  # noqa
add(id="n5 B norm 5120 chain", group="bench serial", dump=NRM, match=NR, groups=1, threads=4, skip=CHAIN, cold=False,
    bytes=0.04e6, us=5.52, src=N5)
add(id="n5 F norm 5120 fast bracket", group="bench serial", dump=NRM, match=NR, groups=1, threads=4, skip=FAST,
    cold=False, bytes=0.04e6, us=5.62, src=N5)
add(id="n5 H norm 1280 chain", group="bench serial", dump=NRM, match=ex("RowsP<NormRows<1280u, 4u> > @wg512"),
    groups=1, threads=4, skip="B003-B019", cold=False, bytes=0.01e6, us=3.54, src=N5)
add(id="n5 I norm 1280 fast bracket", group="bench serial", dump=NRM, match=ex("RowsP<NormRows<1280u, 4u> > @wg512"),
    groups=1, threads=4, skip="B020-B032", cold=False, bytes=0.01e6, us=2.81, src=N5)
add(id="n5 E1 fast norm V1 alone", group="bench serial", dump=NRM, match=ex("RowsP<NormRowsFF<5120u, 4u, 1u> > @wg512"),
    groups=1, threads=4, skip="B017-B030,B040-B070", cold=False, bytes=0.04e6, us=5.62, src=N5)
add(id="n5 E2 fast norm, no fallback", group="bench serial", dump=NRM,
    match=ex("RowsP<NormRowsFF<5120u, 4u, 2u> > @wg512"), groups=1, threads=4, skip="B026-B060", cold=False,
    bytes=0.04e6, us=4.69, src=N5)
add(id="n5 E3 fast sum, no check", group="bench serial", dump=NRM, match=ex("RowsP<NormRowsFF<5120u, 4u, 3u> > @wg512"),
    groups=1, threads=4, skip="B026-B060", cold=False, bytes=0.04e6, us=4.69, src=N5)
add(id="n5 E0 fast norm, two roots", group="bench serial", dump=NRM,
    match=ex("RowsP<NormRowsFF<5120u, 4u, 0u> > @wg512"), groups=1, threads=4, skip="B027-B040,B050-B090",
    cold=False, bytes=0.04e6, us=11.56, src=N5)
for wg, groups, us, lab in [(512, 13, 9.69, "C"), (128, 50, 5.73, "N"), (64, 100, 5.73, "O")]:
    add(id=f"n5 {lab} mix dots alone @wg{wg}", group="bench fp64 rows", dump=NRM,
        match=ex(f"RowsP<HcDotsRows<5120u, 8u> > @wg{wg}"), wg=wg, groups=groups, threads=200, cold=False,
        bytes=2.07e6, us=us, src=N5)
for wg, groups, chain_us, ff_us, lc, lf in [(512, 13, 9.90, 9.90, "A", "G"), (128, 51, 9.06, 6.04, "J", "L"),
                                            (64, 102, 9.27, 6.04, "K", "M")]:
    for path, skip, us, lab in [("chain", CHAIN, chain_us, lc), ("fast", FAST, ff_us, lf)]:
        add(id=f"n5 {lab} norm({path}) + mix dots @wg{wg}", group="bench fused", wg=wg, groups=groups, cold=False,
            bytes=2.11e6, us=us, src=N5,
            parts=[{"dump": NRM, "match": NR, "threads": 4, "skip": skip}, DOTS(wg)])

# ---------------------------------------------------------------- route bench (round18 rt5, warm)
RT5 = DATA + "round18-rt5-route-rows-bench.txt"
add(id="rt5 C mix finish alone (1 sub-group)", group="bench serial", dump=RTR, match=ex("RowsP<HcFinishRows>"),
    groups=1, threads=1, trips={0: 8, 1: 8, 2: 20}, cold=False, bytes=0.01e6, us=6.67, src=RT5)
add(id="rt5 D shared gate+up rows alone", group="bench dense warm", dump=RTR,
    match=ex("RowsP<RowsPair<DenseRows<GemvQ8P<160u, ActF32> >, DenseRows<GemvQ8P<160u, ActF32> > > >"), groups=48,
    threads=768, cold=False, bytes=4.18e6, us=6.56, src=RT5)
add(id="rt5 H router scores only", group="bench serial", dump=RTR, match=ex("RouteT"), groups=1, cold=False,
    bytes=0.01e6, us=0.94, src=RT5)
for lab, us, two in [("B", 21.35, False), ("K", 9.17, True)]:
    add(id=f"rt5 {lab} RouteP alone (two={two})", group="bench branchy", dump=RTR, match=ex("RoutePRows<NoRows>"),
        groups=1, cold=False, bytes=0.01e6, us=us, fit=False, src=RT5)
add(id="rt5 I RouteQ alone", group="bench branchy", dump=RTR, match=ex("RouteQ"), groups=1, cold=False,
    bytes=0.01e6, us=8.65, fit=False, src=RT5)

# ---------------------------------------------------------------- router pick bench (dsv41-work/rp/r3, warm)
RP3 = "/home/steve/dsv41-work/rp/r3/out.txt"
for v, us, fit_ in [(0, 8.65, False), (1, 8.54, False), (2, 2.71, True), (3, 8.12, False), (4, 10.11, False),
                    (5, 1.04, True), (6, 8.54, False), (7, 0.52, True), (8, 6.67, False), (9, 3.33, False),
                    (10, 8.54, False), (11, 4.79, False), (12, 6.04, False), (13, 2.71, False), (14, 3.65, False),
                    (15, 2.81, False)]:
    nm = {0: "Sets<RouteP>", 7: "Sets<Empty>", 12: "Sets<PickC<72> >"}.get(v, f"Sets<PickV<{v}> >")
    add(id=f"rp3 V{v} {nm}", group="bench branchy" if not fit_ else "bench serial", dump=RPK, match=ex(nm),
        groups=1, cold=False, bytes=0.004e6, us=us, fit=fit_, src=RP3)

# ---------------------------------------------------------------- engram gate bench (dsv41-work/eg/r2, warm)
add(id="eg2 A engram chains (engine82 code, warm)", group="bench serial", dump=ENG, match=ex("EngramGateP @wg32"),
    wg=32, groups=4, trips={0: 160, 1: 160}, cold=False, bytes=0.26e6, us=96.14,
    src="/home/steve/dsv41-work/eg/r2/bench_engram_ff.txt")

# ---------------------------------------------------------------- dense rows for 16-token blocks (round18 d3 / d4, cold)
D3, D4 = DATA + "round18-d3-dense-m16-decode-variants.txt", DATA + "round18-d4-dense-m16-q6k-forms.txt"
SH = {40: (6144, 8.36), 160: (1792, 9.75), 256: (864, 7.52), 72: (864, 2.12), 128: (768, 3.34)}
Q8 = {  # C: [(form label, G, R, D, V, us)] from d3; engine = GemvQ8P (same code as D0V0)
    40: [("engine G4 R4", 4, 4, None, None, 105.1)] + [
        (f"G4R4 D{d}V{v}", 4, 4, d, v, u) for (d, v), u in zip(
            [(0, 0), (1, 0), (2, 0), (0, 1), (0, 2), (0, 3), (2, 1), (2, 2), (2, 3)],
            [101.1, 155.2, 132.0, 100.8, 97.5, 96.7, 132.0, 131.2, 134.4])] + [
        (f"G8R2 D{d}V{v}", 8, 2, d, v, u) for (d, v), u in zip(
            [(0, 0), (1, 0), (2, 0), (0, 1), (0, 2), (0, 3), (2, 1), (2, 2), (2, 3)],
            [105.4, 126.0, 113.2, 105.7, 99.0, 105.8, 112.7, 112.1, 112.7])],
    160: [("engine G4", 4, 1, None, None, 80.9)] + [
        (f"G4 D{d}V{v}", 4, 1, d, v, u) for (d, v), u in zip(
            [(0, 0), (1, 0), (2, 0), (0, 1), (0, 2), (0, 3), (2, 1), (2, 2), (2, 3)],
            [80.2, 98.4, 89.3, 80.7, 80.0, 79.4, 88.9, 83.1, 86.9])] + [
        (f"G8R2 D{d}V{v}", 8, 2, d, v, u) for (d, v), u in zip(
            [(0, 0), (1, 0), (2, 0), (0, 1), (0, 2), (0, 3), (2, 1), (2, 2), (2, 3)],
            [70.3, 97.2, 85.3, 70.6, 66.6, 66.7, 85.0, 86.2, 88.2])],
    256: [("engine G4", 4, 1, None, None, 67.0)] + [
        (f"G4 D{d}V{v}", 4, 1, d, v, u) for (d, v), u in zip(
            [(0, 0), (1, 0), (2, 0), (0, 1), (0, 2), (0, 3), (2, 1), (2, 2), (2, 3)],
            [65.6, 82.4, 74.2, 65.5, 66.1, 65.0, 72.5, 70.3, 73.4])] + [
        (f"G8R2 D{d}V{v}", 8, 2, d, v, u) for (d, v), u in zip(
            [(0, 0), (1, 0), (2, 0), (0, 1), (0, 2), (0, 3), (2, 1), (2, 2), (2, 3)],
            [52.7, 82.2, 71.8, 53.1, 61.6, 62.3, 66.6, 66.4, 66.9])],
    72: [("engine G4", 4, 1, None, None, 26.8)] + [
        (f"G4 D{d}V{v}", 4, 1, d, v, u) for (d, v), u in zip(
            [(0, 0), (1, 0), (2, 0), (0, 1), (0, 2), (0, 3), (2, 1), (2, 2), (2, 3)],
            [26.6, 32.6, 29.6, 26.6, 26.0, 26.5, 29.4, 28.9, 28.1])] + [
        (f"G4R2 D{d}V{v}", 4, 2, d, v, u) for (d, v), u in zip(
            [(0, 0), (1, 0), (2, 0), (0, 1), (0, 2), (0, 3), (2, 1), (2, 2), (2, 3)],
            [23.8, 29.8, 27.1, 23.6, 23.3, 23.6, 27.3, 26.6, 26.6])],
    128: [("engine G4", 4, 1, None, None, 37.1)] + [
        (f"G4 D{d}V{v}", 4, 1, d, v, u) for (d, v), u in zip(
            [(0, 0), (1, 0), (2, 0), (0, 1), (0, 2), (0, 3), (2, 1), (2, 2), (2, 3)],
            [36.9, 46.7, 42.6, 36.9, 37.7, 37.0, 42.8, 40.4, 41.5])] + [
        (f"G2R4 D{d}V{v}", 2, 4, d, v, u) for (d, v), u in zip(
            [(0, 0), (1, 0), (2, 0), (0, 1), (0, 2), (0, 3), (2, 1), (2, 2), (2, 3)],
            [34.4, 101.8, 83.9, 34.3, 36.6, 32.6, 80.9, 80.6, 80.8])],
}


def dense_name(kern, g, r):
    return f"DenseRowsG<{kern}, {g}u>" if r == 1 else f"DenseRowsGR<{kern}, {g}u, {r}u>"


def dense_groups(rows, g, r, mt=16):
    ng = (mt + g - 1) // g
    return ((rows + r - 1) // r * ng + 15) // 16


for c, forms in Q8.items():
    rows, mb = SH[c]
    for lab, g, r, d, v, us in forms:
        kern = f"GemvQ8P<{c}u, ActF32>" if d is None else f"Q8V<{c}u, {d}u, {v}u>"
        add(id=f"d3 Q8_0 {rows}x{c * 32} {lab}", group="bench dense m16", dump=DEN, match=ex(dense_name(kern, g, r)),
            groups=dense_groups(rows, g, r), bytes=mb * 1e6 + 16 * c * 32 * 4, us=us, src=D3,
            trips_bytes=(ACT, g * c * 32 * 4))
Q6 = {5: (6144, 6.49, [("engine G4 R4", 4, 4, 114.8), ("G4", 4, 1, 107.0), ("G8", 8, 1, 109.5), ("G4 R2", 4, 2, 116.1),
                       ("G8 R2", 8, 2, 107.5), ("G2 R4", 2, 4, 131.5)]),
      20: (1792, 7.54, [("engine G4", 4, 1, 144.5), ("G8", 8, 1, 92.8), ("G4 R2", 4, 2, 89.6), ("G4 R4", 4, 4, 95.0),
                        ("G8 R2", 8, 2, 92.7), ("G2 R4", 2, 4, 138.2)]),
      32: (864, 5.81, [("engine G4", 4, 1, 77.9), ("G8", 8, 1, 87.0), ("G4 R2", 4, 2, 75.5), ("G4 R4", 4, 4, 84.3),
                       ("G8 R2", 8, 2, 80.8), ("G2 R4", 2, 4, 124.6)]),
      16: (768, 2.58, [("engine G4", 4, 1, 72.0), ("G8", 8, 1, 41.1), ("G4 R2", 4, 2, 39.7), ("G4 R4", 4, 4, 45.9),
                       ("G8 R2", 8, 2, 54.0), ("G2 R4", 2, 4, 51.6)])}
for nb, (rows, mb, forms) in Q6.items():
    for lab, g, r, us in forms:
        add(id=f"d4 Q6_K {rows}x{nb * 256} {lab}", group="bench dense m16", dump=DEN,
            match=ex(dense_name(f"GemvQ6KP<{nb}u, ActF32>", g, r)), groups=dense_groups(rows, g, r),
            bytes=mb * 1e6 + 16 * nb * 256 * 4, us=us, src=D4, trips_bytes=(ACT, g * nb * 256 * 4))
