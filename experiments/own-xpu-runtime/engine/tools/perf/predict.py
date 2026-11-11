#!/usr/bin/env python3
"""Predict one kernel launch's GPU time on a B70 (Xe2, BMG-G31) from its machine code, without running it.

  predict.py DUMP_DIR --match REGEX --wg 512 --groups N [--threads N] [--bytes B] [--warm] [--loads warm]
             [--trips 1=3,2=16] [--skip B004-B032] [--hot REGEX] [--explain]
  predict.py --table [--cases cases.py] [--only REGEX] [--csv OUT]   predicted vs measured for every calibration case
  predict.py --fit   [--cases cases.py]                              refit the free constants -> calib.json

Model (per launch, event time = command_end - command_start, as the engine profile and the benches measure):

  T = launch + max(T_issue, T_fp64, T_mem, T_lat)
    T_issue = busiest XVE's issue cycles / (clock x dual)        all threads' instructions, per pipe cost below
    T_fp64  = busiest XVE's long-pipe (FP64) cycles / clock       df ops cost exec / fp64_lanes cycles
    T_mem   = DRAM bytes / bw_dram  (+ L2-resident bytes / bw_l2 when --warm)
    T_lat   = waves x one thread's critical path: a replay of the thread's instruction stream with the compiler's own
              dependence marks (SWSB: F@n / I@n / L@n / M@n distances, $n send tokens, sync.allrd / allwr / bar)
              and measured latencies (float op ~8.6 ns, dependent double op ~26 ns, global load ~1 us cold, ...)
  Issue cost per instruction: float / int pipes ceil(exec x bits / 512) cycles (SIMD16 32-bit hardware: a SIMD32
  op = 2 cycles); FP64 exec / fp64_lanes; math exec / math_lanes; send send_cyc; sync / branch 1.
  Threads are spread over the Xe-cores work-group by work-group (32 cores x 8 XVEs; 8 threads per XVE in 128-GRF
  mode, 4 in 256-GRF mode); a launch with more work-groups than fit runs in waves.
  Several thread kinds in one launch (a RowsPair launch: a few serial rows beside many dense rows): --parts, see
  cases.py; each part has its own code, thread count, loop trips and skipped blocks.

Dynamic counts: every instruction once, loops x trips (loop ids from isa_census.py), blocks in --skip left out
(a runtime branch that this launch never takes). Constants: DEFAULTS below, overridden by calib.json (--fit).
"""
import argparse, collections, importlib.util, json, math, os, re, sys

sys.dont_write_bytecode = True  # no __pycache__ in the engine tree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import isa_census as ic  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CALIB = os.path.join(HERE, "calib.json")

DEFAULTS = {
    # hardware (B70: 32 Xe-cores x 8 XVEs, SIMD16 ALUs)
    "clk_ghz": 2.4, "xecores": 32, "xve_per_core": 8, "thr_per_xve_128": 8, "thr_per_xve_256": 4,
    "slm_per_core_kb": 128,
    # issue
    "dual": 1.0,          # issue rate: instructions per clock per XVE over all its threads (fitted; < 1 = stalls)
    "fp64_lanes": 2.0,    # FP64 lanes per clock per XVE (16 = full rate, 1 = 1/16, 0.5 = 1/32)
    "math_lanes": 4.0,    # math (EM) pipe lanes per clock
    "send_cyc": 1.0,      # issue cycles per send
    # latencies (ns), result ready after the instruction's last issue cycle
    "lat_f": 2.0,         # float pipe result latency (fitted; a measured dependent float add chain: ~8.6 ns per op)
    "lat_i": 2.0,         # int pipe result latency (fitted; moves and address math run here)
    "lat_l": 10.0,        # FP64 pipe result latency (fitted; fp64_step() = the dependent SIMD32 double add it implies)
    "lat_m": 6.0,         # math pipe
    "lat_gl_cold": 600.0,   # global load, data in DRAM (a measured single round trip: ~1 us)
    "lat_gl_warm": 150.0,   # global load, data in L2
    "lat_gl_hot": 120.0,    # global load the case marks hot (--hot / "hot": activations every work-group re-reads)
    "lat_slm": 30.0,      # local memory load
    "lat_fill": 300.0,    # spill fill (scratch)
    "lat_bar": 50.0,      # work-group barrier (signal -> wait)
    "lat_fence": 300.0,   # memory fence
    "src_ns": 5.0,        # a send's sources are read this long after issue ($n.src)
    # launch and memory
    "launch_ns": 520.0,   # event-timed launch floor (empty kernel 0.52 us in rp r3 V7)
    "wave_ns": 300.0,     # extra cost per extra wave of work-groups (dispatch ramp)
    "bw_dram": 550.0,     # GB/s
    "bw_l2": 1500.0,      # GB/s (data already in the 18 MB L2: warm benches)
    "port_bpc": 110.0,    # bytes per clock per Xe-core returned by global loads (L1 / data port), all threads' loads
    "slm_bpc": 64.0,      # bytes per clock per Xe-core of local-memory loads
    "line": 64.0,         # cache line: a cold load reading fewer bytes shares its line with its neighbours (see latency)
    "smooth_k": 8.0,      # T_core = (sum of bounds^k)^(1/k): k large = the plain max, smaller = bounds overlap less
    "fp64_step_ns": 26.0,  # measured dependent SIMD32 double add (reference only: compare fp64_step(p))
}
FREE = ["dual", "fp64_lanes", "lat_f", "lat_i", "lat_l", "lat_gl_cold", "lat_gl_warm", "lat_gl_hot", "lat_slm",
        "lat_bar", "lat_m", "lat_fill", "launch_ns", "wave_ns", "bw_dram", "bw_l2", "port_bpc", "slm_bpc", "smooth_k"]
BOUNDS = {"dual": (0.25, 2.0), "fp64_lanes": (0.25, 8.0), "lat_f": (0.4, 10), "lat_i": (0.4, 10), "lat_l": (3, 40),
          "lat_gl_cold": (300, 2500), "lat_gl_warm": (100, 1500), "lat_gl_hot": (40, 1000), "lat_slm": (10, 400),
          "lat_bar": (5, 2000), "lat_m": (2, 60), "lat_fill": (30, 1500), "launch_ns": (300, 1500), "wave_ns": (0, 3000),
          # bandwidths kept physical: the output head streams at 572 GB/s, the card's peak is ~608
          "bw_dram": (450, 640), "bw_l2": (800, 4000), "port_bpc": (8, 512), "slm_bpc": (8, 512),
          "smooth_k": (1.0, 32.0)}


def load_params(path=CALIB):
    p = dict(DEFAULTS)
    if path and os.path.exists(path):
        p.update(json.load(open(path)).get("params", {}))
    return derive(p)


def derive(p):
    # lat_l and fp64_lanes are both fitted (the engram chains pin their combination; the norm / dot benches the
    # rate); fp64_step() shows the dependent SIMD32 double add they imply, to compare with the measured ~26 ns
    return p


def fp64_step(p):
    """dependent SIMD32 double add (two SIMD16 halves, each half waits for the same half of the previous op):
    max(both halves' issue, one half's issue + lat_l)"""
    half = 16.0 / p["fp64_lanes"] / p["clk_ghz"]
    return max(2 * half, half + p["lat_l"])


# ---------------------------------------------------------------------------------------------------------------
# one thread: dynamic instruction stream, issue cycles per pipe, critical path

RE_DIST = re.compile(r"(?:^|,)\s*([AFILM]?)@(\d+)")
RE_TOK = re.compile(r"\$(\d+)(\.dst|\.src)?")


def swsb_of(ins):
    if not hasattr(ins, "_sw"):
        sw = ins.swsb or ""
        dist = [(p or "A", int(n)) for p, n in RE_DIST.findall(sw)]
        toks = [(int(t), k) for t, k in RE_TOK.findall(sw)]
        ins._sw = (dist, toks)
    return ins._sw


def pipe_of(ins):
    return {"float": "F", "int": "I", "long": "L", "math": "M"}.get(ins.pipe, "")


def issue_cycles(ins, p):
    c = ins.cls
    if c.startswith("send."):
        return p["send_cyc"]
    if c.startswith(("sync.", "ctrl.")):
        return 1.0
    pp = pipe_of(ins)
    if pp == "L":
        if "df" in ins.types:
            return max(1.0, ins.exec_size / p["fp64_lanes"])
        return max(1.0, math.ceil(ins.exec_size * 64 / 512))
    if pp == "M":
        return max(1.0, ins.exec_size / p["math_lanes"])
    return max(1.0, math.ceil(ins.exec_size * ins.bits / 512))


def latency(ins, p, cold, hot=None):
    c = ins.cls
    if c.startswith("send."):
        if c in ("send.load.global", "send.atomic"):
            if hot is not None and c == "send.load.global" and hot.search(ins.text):
                return p["lat_gl_hot"]
            far = p["lat_gl_cold"] if cold else p["lat_gl_warm"]
            if c == "send.load.global" and ins.bytes and ins.bytes < p["line"]:
                # a narrow load (a scalar scale, one row's word) shares its cache line with the next loads of the
                # stream: on average only bytes / line of them miss
                return p["lat_gl_hot"] + (far - p["lat_gl_hot"]) * ins.bytes / p["line"]
            return far
        if c == "send.load.slm":
            return p["lat_slm"]
        if c == "send.fill":
            return p["lat_fill"]
        if c == "send.fence":
            return p["lat_fence"]
        return p["src_ns"]  # stores, spills, barrier signal, eot: nothing waits on a result
    pp = pipe_of(ins)
    return {"F": p["lat_f"], "I": p["lat_i"], "L": p["lat_l"], "M": p["lat_m"]}.get(pp, 0.0)


def parse_ranges(k, skip):
    """'B004-B032' / 'B010' / 'i100-i200' (instruction indices) -> set of instruction indices"""
    out = set()
    if not skip:
        return out
    bfirst = {}
    for i in k.insts:
        bfirst.setdefault(i.block, i.idx)
    blast = {}
    for i in k.insts:
        blast[i.block] = i.idx
    for s in (skip.split(",") if isinstance(skip, str) else skip):
        s = s.strip()
        m = re.fullmatch(r"B(\d+)(?:-B(\d+))?", s)
        if m:
            a, b = int(m.group(1)), int(m.group(2) or m.group(1))
            for bid in range(a, b + 1):
                if bid in bfirst:
                    out.update(range(bfirst[bid], blast[bid] + 1))
            continue
        m = re.fullmatch(r"i(\d+)-i?(\d+)", s)
        if m:
            out.update(range(int(m.group(1)), int(m.group(2)) + 1))
            continue
        raise ValueError(f"bad skip range {s!r}")
    return out


def dyn_path(k, trips=None, skip=None):
    trips = {int(a): float(b) for a, b in (trips or {}).items()}
    sk = parse_ranges(k, skip)
    kids = collections.defaultdict(list)
    for n, L in enumerate(k.loops):
        kids[L.parent].append(n)

    def walk(first, last, parent):
        i = first
        for li in sorted(kids[parent], key=lambda j: k.loops[j].first):
            L = k.loops[li]
            if L.first < first or L.last > last:
                continue
            for j in range(i, L.first):
                if j not in sk:
                    yield j
            t = trips.get(li, 1.0)
            whole = int(t)
            for _ in range(whole):
                yield from walk(L.first, L.last, li)
            if t - whole > 1e-9:  # fractional trips: the average thread (issue counts only)
                for j in walk(L.first, L.last, li):
                    yield (j, t - whole)
            i = L.last + 1
        for j in range(i, last + 1):
            if j not in sk:
                yield j

    return walk(0, len(k.insts) - 1, -1)


def simulate(k, p, trips=None, skip=None, cold=True, cap=3_000_000, hot=None):
    """one thread. Issue cycles count fractional trips (the average thread); the critical path replays the
    rounded-up trip count (the slowest thread)."""
    clk = p["clk_ghz"]
    hot = re.compile(hot) if hot else None
    t_issue = 0.0
    hist = {x: collections.deque(maxlen=32) for x in "FILMA"}
    tok_dst, tok_src = {}, {}
    tok_cls = {}
    bar_t = 0.0
    blk = collections.Counter()      # ns of the thread's timeline spent per block (issue + stalls)
    why = collections.Counter()      # ns of stall by what was waited for
    cyc = collections.Counter()
    dyn = collections.Counter()
    nbytes = collections.Counter()
    last = 0.0
    n = 0
    for item in dyn_path(k, trips, skip):
        w = 1.0
        if isinstance(item, tuple):
            item, w = item
        ins = k.insts[item]
        ic_ = issue_cycles(ins, p)
        pp = pipe_of(ins)
        grp = "send" if ins.cls.startswith("send.") else ("L" if pp == "L" else "M" if pp == "M" else
                                                          "F" if pp == "F" else "I")
        cyc[grp] += ic_ * w
        dyn[ins.cls] += w
        if ins.bytes:
            nbytes[ins.cls] += ins.bytes * w
        n += 1
        if n > cap:
            raise RuntimeError(f"dynamic path over {cap} instructions: lower the trips")
        dist, toks = swsb_of(ins)
        ready, reason = t_issue, ""

        def upd(t, r):
            nonlocal ready, reason
            if t > ready:
                ready, reason = t, r
        for pipe, d in dist:
            h = hist[pipe]
            if pipe == "A":
                if h:
                    upd(max(list(h)[-d:]), "pipe A")
            elif len(h) >= d:
                upd(h[-d], "pipe " + pipe)
        is_send = ins.cls.startswith("send.")
        set_tok = None
        for t, kind in toks:
            if is_send and not kind:
                set_tok = t
                continue
            if kind == ".src":
                upd(tok_src.get(t, 0.0), "send src")
            else:
                upd(tok_dst.get(t, 0.0), tok_cls.get(t, "send"))
        if ins.cls == "sync.allrd":
            for t in ins.sync_toks or tuple(tok_src):
                upd(tok_src.get(t, 0.0), "send src")
        elif ins.cls == "sync.allwr":
            for t in ins.sync_toks or tuple(tok_dst):
                upd(tok_dst.get(t, 0.0), tok_cls.get(t, "send"))
        elif ins.cls == "sync.bar":
            upd(bar_t, "barrier")
        if ready > t_issue:
            why[reason] += ready - t_issue
        t_prev = t_issue
        start = ready
        t_issue = start + ic_ / clk
        done = t_issue + latency(ins, p, cold, hot)
        if is_send:
            if ins.cls == "send.barrier":
                bar_t = start + p["lat_bar"]
            if set_tok is not None:
                tok_dst[set_tok] = done
                tok_src[set_tok] = start + p["src_ns"]
                tok_cls[set_tok] = ins.cls.replace("send.", "")
        elif pp:
            hist[pp].append(done)
            hist["A"].append(done)
        blk[ins.block] += t_issue - t_prev
        last = max(last, t_issue)
    why["issue (own)"] = last - sum(why.values())
    return {"crit_ns": last, "cycles": cyc, "dyn": dyn, "bytes": nbytes, "n": sum(dyn.values()), "blocks": blk,
            "why": why}


# ---------------------------------------------------------------------------------------------------------------
# one launch

_KCACHE = {}


def find_kernel(dump, match):
    key = (dump, match)
    if key not in _KCACHE:
        ks = ic.load_dir([dump], match)
        if not ks:
            raise LookupError(f"no kernel matching {match!r} in {dump}")
        if len(ks) > 1:
            exact = [x for x in ks if x.name == match]
            if len(exact) == 1:
                ks = exact
            else:
                names = "\n  ".join(x.name for x in ks[:8])
                raise LookupError(f"{len(ks)} kernels match {match!r} in {dump}:\n  {names}")
        _KCACHE[key] = ks[0]
    return _KCACHE[key]


_SCACHE = {}
SIM_KEYS = {"clk_ghz", "fp64_lanes", "math_lanes", "send_cyc", "src_ns", "line"}  # + every lat_*: what simulate() reads


def thread_model(k, p, trips, skip, cold, hot=None):
    key = (id(k), json.dumps(trips, sort_keys=True), str(skip), cold, hot,
           json.dumps({x: p[x] for x in sorted(p) if x in SIM_KEYS or x.startswith("lat_")}, sort_keys=True))
    if key not in _SCACHE:
        if len(_SCACHE) > 3000:  # a fit visits many parameter sets: keep memory bounded
            _SCACHE.clear()
        _SCACHE[key] = simulate(k, p, trips, skip, cold, hot=hot)
    return _SCACHE[key]


def predict_launch(parts, wg, groups, p, bytes_dram=0.0, bytes_l2=0.0, cold=True, extra_ns=0.0):
    """parts: list of dicts {kernel: Kernel, threads: N, trips: {}, skip: '', hot: REGEX}. Returns the bounds."""
    clk = p["clk_ghz"]
    k0 = parts[0]["kernel"]
    simd = k0.simd or 32
    tpw = max(1, wg // simd)                       # threads per work-group
    grf = max(pp["kernel"].grf for pp in parts)
    slots = p["xve_per_core"] * (p["thr_per_xve_256"] if grf > 128 else p["thr_per_xve_128"])
    wg_res = max(1, slots // tpw)                  # resident work-groups per Xe-core
    cores = min(p["xecores"], groups)
    wg_per_core = math.ceil(groups / p["xecores"])
    waves = math.ceil(wg_per_core / wg_res)
    # XVEs in use: the resident threads of a core spread over its 8 XVEs (several small work-groups share a core)
    xves = cores * min(p["xve_per_core"], tpw * min(wg_per_core, wg_res))
    total_issue = 0.0
    total_long = 0.0
    total_gl = 0.0
    total_slm = 0.0
    t_lat = 0.0
    crit = 0.0
    detail = []
    nthreads = 0
    for pp in parts:
        k = pp["kernel"]
        th = thread_model(k, p, pp.get("trips"), pp.get("skip"), pp.get("cold_lat", cold), pp.get("hot"))
        n = pp["threads"]
        nthreads += n
        c = th["cycles"]
        isz = sum(c.values())
        total_issue += n * isz
        total_long += n * c.get("L", 0.0)
        total_gl += n * th["bytes"].get("send.load.global", 0.0)
        total_slm += n * th["bytes"].get("send.load.slm", 0.0)
        crit = max(crit, th["crit_ns"])
        # a part with fewer threads than one work-group (the serial row of a RowsPair launch) runs once, in the
        # first wave; the dense part's threads fill every wave
        t_lat = max(t_lat, th["crit_ns"] * (waves if n > tpw else 1))
        detail.append((k.name, n, th))
    # busiest XVE: threads spread evenly over the XVEs in use, at least one whole thread's work
    per_xve_issue = max(total_issue / xves, max(sum(d[2]["cycles"].values()) for d in detail))
    per_xve_long = max(total_long / xves, max(d[2]["cycles"].get("L", 0.0) for d in detail))
    t_issue = per_xve_issue / (clk * p["dual"])
    t_fp64 = per_xve_long / clk
    t_mem = bytes_dram / p["bw_dram"] + bytes_l2 / p["bw_l2"]  # bytes / (GB/s) = ns
    # data port: every byte any thread loads (cache hits included: the activations each sub-group re-reads)
    t_port = total_gl / cores / (p["port_bpc"] * clk) + total_slm / cores / (p["slm_bpc"] * clk)
    bounds = {"issue": t_issue, "fp64": t_fp64, "latency": t_lat, "memory": t_mem, "port": t_port}
    k_ = p["smooth_k"]
    top = max(bounds.values())
    core = top * sum((v / top) ** k_ for v in bounds.values()) ** (1.0 / k_) if top > 0 else 0.0
    bound = max(bounds, key=bounds.get)
    launch = p["launch_ns"] + p["wave_ns"] * (waves - 1)
    return {"ns": launch + core + extra_ns, "launch": launch, "issue": t_issue, "fp64": t_fp64, "latency": t_lat,
            "memory": t_mem, "port": t_port, "bound": bound, "waves": waves, "xves": xves, "threads": nthreads,
            "detail": detail, "floor": launch + t_mem, "load_bytes": total_gl + total_slm}


# ---------------------------------------------------------------------------------------------------------------
# calibration cases

def load_cases(path):
    spec = importlib.util.spec_from_file_location("perf_cases", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.CASES


def trips_from_bytes(k, pattern, nbytes):
    """trips of a kernel's single top-level loop from the bytes one sub-group must load with the matching loads
    (e.g. the activations of a dense form whose K loop the compiler did not fully unroll): (bytes - bytes of the
    matching loads outside the loop) / bytes of those inside one iteration"""
    top = [n for n, L in enumerate(k.loops) if L.parent == -1]
    if len(top) != 1:
        return {}
    L = k.loops[top[0]]
    rx = re.compile(pattern)
    sel = [i for i in k.insts if i.cls == "send.load.global" and rx.search(i.text)]
    inside = sum(i.bytes for i in sel if L.first <= i.idx <= L.last)
    if not inside:
        return {}
    return {top[0]: max(1.0, (nbytes - (sum(i.bytes for i in sel) - inside)) / inside)}


def run_case(c, p):
    cold = c.get("cold", True)
    parts = []
    for pt in c.get("parts") or [{"match": c["match"], "threads": c.get("threads")}]:
        k = find_kernel(pt.get("dump", c.get("dump")), pt["match"])
        thr = pt.get("threads") or c["groups"] * c["wg"] // (k.simd or 32)
        # loads: "cold" = global loads wait the DRAM latency (weights streamed once per step), "warm" = the L2
        # latency (activations the previous launch wrote, or a bench repeating one launch); default from cold
        loads = pt.get("loads", c.get("loads", "cold" if cold else "warm"))
        trips = pt.get("trips", c.get("trips"))
        tb = pt.get("trips_bytes", c.get("trips_bytes"))  # (load regex, bytes per sub-group): loop trips from bytes
        if trips is None and tb and k.loops:
            trips = trips_from_bytes(k, *tb)
        parts.append({"kernel": k, "threads": thr, "trips": trips,
                      "skip": pt.get("skip", c.get("skip")), "hot": pt.get("hot", c.get("hot")),
                      "cold_lat": loads == "cold"})
    b = c.get("bytes", 0.0)
    return predict_launch(parts, c["wg"], c["groups"], p, bytes_dram=b if cold else 0.0,
                          bytes_l2=0.0 if cold else b, cold=cold, extra_ns=c.get("extra_ns", 0.0))


def table(cases, p, only=None, csv=None, show=True):
    rows = []
    for c in cases:
        if only and not re.search(only, c["id"]):
            continue
        try:
            r = run_case(c, p)
        except Exception as e:  # noqa: BLE001
            print(f"!! {c['id']}: {e}", file=sys.stderr)
            continue
        pred = r["ns"] / 1000.0
        meas = c["us"]
        rows.append((c, r, pred, meas))
    if show:
        print(f"{'case':44s} {'meas us':>8s} {'pred us':>8s} {'err':>6s}  {'bound':8s} {'issue':>6s} {'fp64':>6s} "
              f"{'lat':>6s} {'mem':>6s} {'port':>6s} {'floor':>6s} {'meas/floor':>10s}")
        for c, r, pred, meas in rows:
            err = (pred - meas) / meas * 100
            print(f"{c['id'][:44]:44s} {meas:8.2f} {pred:8.2f} {err:+5.0f}%  {r['bound']:8s} {r['issue']/1e3:6.2f} "
                  f"{r['fp64']/1e3:6.2f} {r['latency']/1e3:6.2f} {r['memory']/1e3:6.2f} {r['port']/1e3:6.2f} "
                  f"{r['floor']/1e3:6.2f} "
                  f"{meas / (r['floor'] / 1e3):10.1f}")
        stats(rows)
    if csv:
        import csv as csvmod
        with open(csv, "w", newline="") as f:
            w = csvmod.writer(f)
            w.writerow(["case", "group", "fitted", "per_step", "measured_us", "predicted_us", "error_pct", "bound",
                        "issue_us", "fp64_us", "latency_us", "memory_us", "port_us", "floor_us", "waves", "threads",
                        "source"])
            for c, r, pred, meas in rows:
                w.writerow([c["id"], c.get("group", ""), int(c.get("fit", True)), c.get("per_step", ""),
                            f"{meas:.3f}", f"{pred:.3f}", f"{(pred - meas) / meas * 100:.1f}", r["bound"]]
                           + [f"{r[x] / 1e3:.3f}" for x in ("issue", "fp64", "latency", "memory", "port", "floor")]
                           + [r["waves"], r["threads"], c.get("src", "")])
    return rows


REF_LAUNCH_US, REF_BW = 0.52, 550.0  # reference floor: empty launch (rp r3 V7) + DRAM bytes at 550 GB/s


def rank(rows, top=40):
    """engine cases with launches per step: time above the reference floor per answer step, and the model's view of
    what holds each kernel there (its largest bounds)"""
    out = []
    for c, r, pred, meas in rows:
        if "per_step" not in c:
            continue
        floor = REF_LAUNCH_US + c.get("bytes", 0.0) / REF_BW / 1e3
        b = sorted(((k, r[k]) for k in ("issue", "fp64", "latency", "memory", "port")), key=lambda x: -x[1])
        out.append((c, meas, floor, (meas - floor) * c["per_step"], b, pred))
    out.sort(key=lambda x: -x[3])
    print(f"\ntime above the floor per answer step (card 2; floor = {REF_LAUNCH_US} us launch + bytes at {REF_BW:.0f} GB/s)")
    print(f"{'case':44s} {'n/step':>6s} {'meas us':>8s} {'floor':>6s} {'x floor':>7s} {'above us/step':>13s}  "
          f"model: largest bounds (us)")
    for c, meas, floor, above, b, pred in out[:top]:
        print(f"{c['id'][:44]:44s} {c['per_step']:6d} {meas:8.2f} {floor:6.2f} {meas / floor:7.1f} {above:13.1f}  "
              + ", ".join(f"{k} {v / 1e3:.1f}" for k, v in b[:2]) + f" (pred {pred:.1f})")
    return out


def stats(rows, label="all"):
    if not rows:
        return
    by = collections.defaultdict(list)
    for c, r, pred, meas in rows:
        e = math.log(pred / meas)
        by[c.get("group", "?")].append(e)
        by["all"].append(e)
    print("\nerror by group (log-ratio based): median |err|, mean |err|, worst, n; within 25 % / 50 %")
    for g, es in sorted(by.items(), key=lambda x: (x[0] != "all", x[0])):
        a = sorted(abs(math.exp(e) - 1) for e in es)
        w = max(es, key=abs)
        print(f"  {g:22s} {100 * a[len(a) // 2]:5.0f}% {100 * sum(a) / len(a):5.0f}% {100 * (math.exp(w) - 1):+6.0f}%"
              f" n={len(es):3d}; {sum(x <= .25 for x in a):3d} / {sum(x <= .5 for x in a):3d}")


def fit(cases, p, rounds=4):
    """coordinate descent on the FREE constants (log-ratio error, capped per case). Each group of cases weighs
    1 / sqrt(cases in the group), so the 119 dense-bench forms do not drown the engine's few launches."""
    cases = [c for c in cases if c.get("fit", True)]
    ng = collections.Counter(c.get("group", "?") for c in cases)
    for c in cases:
        c["_w"] = c.get("weight", 1.0) / math.sqrt(ng[c.get("group", "?")])

    def loss(q):
        q = derive(dict(q))
        tot = 0.0
        for c in cases:
            try:
                r = run_case(c, q)
            except Exception:  # noqa: BLE001
                continue
            e = math.log(r["ns"] / 1000.0 / c["us"])
            tot += min(e * e, 1.0) * c["_w"]  # robust: one wild case cannot dominate
        return tot

    best = dict(p)
    cur = loss(best)
    print(f"start loss {cur:.4f}")
    for rd in range(rounds):
        steps = (0.5, 0.7, 0.85, 1.18, 1.4, 2.0) if rd < 2 else (0.8, 0.9, 0.95, 1.05, 1.1, 1.25)
        for name in FREE:
            lo, hi = BOUNDS[name]
            cands = sorted(set(([lo, hi] if rd == 0 else []) + [best[name] * f for f in steps]))
            for v in cands:
                v = min(hi, max(lo, v))
                q = dict(best)
                q[name] = v
                l_ = loss(q)
                if l_ < cur - 1e-9:
                    cur, best = l_, derive(q)
        print(f"round {rd}: loss {cur:.4f}  " + "  ".join(f"{n}={best[n]:.3g}" for n in FREE))
    return best, cur


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dump", nargs="?")
    ap.add_argument("--match")
    ap.add_argument("--wg", type=int, default=512)
    ap.add_argument("--groups", type=int, default=1)
    ap.add_argument("--threads", type=int, help="active threads (sub-groups); default all")
    ap.add_argument("--bytes", type=float, default=0.0, help="bytes read from memory (DRAM, or L2 with --warm)")
    ap.add_argument("--warm", action="store_true", help="data already in L2 (a bench repeating one launch)")
    ap.add_argument("--loads", choices=("cold", "warm"), help="what global loads wait for: DRAM (cold) or L2 (warm: "
                    "activations the previous launch wrote). Default: warm with --warm, else cold")
    ap.add_argument("--trips", default="", help="loop trips: 'L1=3,L0=16' (loop ids from isa_census.py)")
    ap.add_argument("--skip", default="", help="blocks never taken: 'B004-B032,B040'")
    ap.add_argument("--hot", default="", help="regex on load text: loads that hit cache (e.g. d32x64t = the "
                    "activations of the Gemv kernels, re-read by every work-group)")
    ap.add_argument("--explain", action="store_true")
    ap.add_argument("--table", action="store_true")
    ap.add_argument("--fit", action="store_true")
    ap.add_argument("--cases", default=os.path.join(HERE, "cases.py"))
    ap.add_argument("--only")
    ap.add_argument("--csv")
    ap.add_argument("--defaults", action="store_true", help="ignore calib.json")
    ap.add_argument("--calib", default=CALIB, help="constants file to read (and to write with --fit)")
    ap.add_argument("--fit-on", help="--fit: fit only the cases whose id matches this regex (a held-out check: "
                    "e.g. --fit-on '^(n5|rt5|rp3|eg2|d3|d4) ' fits the benches, then --table shows the engine)")
    a = ap.parse_args()
    p = derive(dict(DEFAULTS)) if a.defaults else load_params(a.calib)
    if a.fit:
        cases = load_cases(a.cases)
        fc = [c for c in cases if not a.fit_on or re.search(a.fit_on, c["id"])]
        best, l_ = fit(fc, p)
        json.dump({"params": {n: best[n] for n in FREE}, "loss": l_, "cases": sum(c.get("fit", True) for c in fc),
                   "fit_on": a.fit_on or "all"}, open(a.calib, "w"), indent=1)
        print(f"wrote {a.calib}")
        rank(table(cases, best))
        return
    if a.table:
        rank(table(load_cases(a.cases), p, a.only, a.csv))
        return
    if not (a.dump and a.match):
        ap.error("give DUMP_DIR --match REGEX, or --table / --fit")
    k = find_kernel(a.dump, a.match)
    trips = {int(x.split("=")[0].lstrip("L")): float(x.split("=")[1]) for x in a.trips.split(",") if x}
    th = a.threads or a.groups * a.wg // (k.simd or 32)
    cold_lat = (a.loads or ("warm" if a.warm else "cold")) == "cold"
    r = predict_launch([{"kernel": k, "threads": th, "trips": trips, "skip": a.skip, "hot": a.hot or None,
                         "cold_lat": cold_lat}],
                       a.wg, a.groups, p,
                       bytes_dram=0 if a.warm else a.bytes, bytes_l2=a.bytes if a.warm else 0, cold=not a.warm)
    print(f"{k.name}\n  predicted {r['ns'] / 1e3:.2f} us ({r['bound']}-bound): launch {r['launch'] / 1e3:.2f}, "
          f"issue {r['issue'] / 1e3:.2f}, fp64 {r['fp64'] / 1e3:.2f}, latency {r['latency'] / 1e3:.2f} "
          f"({r['waves']} wave(s)), memory {r['memory'] / 1e3:.2f}, port {r['port'] / 1e3:.2f} "
          f"({r['load_bytes'] / 1e6:.1f} MB loaded by all threads); floor (launch + memory) {r['floor'] / 1e3:.2f} us")
    if a.explain:
        for name, n, t in r["detail"]:
            g = ic.group_counts(t["dyn"])
            print(f"  part {name[:90]}: {n} threads, per thread {t['n']:.0f} instructions, critical path "
                  f"{t['crit_ns'] / 1e3:.2f} us, issue cycles " + " ".join(f"{x}={v:.0f}" for x, v in
                                                                         sorted(t["cycles"].items())))
            print("    dynamic: " + "  ".join(f"{x} {v:.0f}" for x, v in g.items()))
            if t["bytes"]:
                print("    bytes per thread: " + "  ".join(f"{x} {v:.0f}" for x, v in t["bytes"].items()))
            print("    critical path by wait: " + "  ".join(f"{x} {v / 1e3:.2f} us" for x, v in t["why"].most_common()
                                                           if v > 1))
            top = t["blocks"].most_common(8)
            print("    slowest blocks (us on the thread's timeline): " + "  ".join(
                f"B{b:03d} {v / 1e3:.2f}" for b, v in top))


if __name__ == "__main__":
    main()
