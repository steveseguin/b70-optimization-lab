#!/usr/bin/env python3
"""Machine-code census of IGC assembly dumps (.asm) for Xe2 (B70 / BMG-G31) kernels.

  isa_census.py DUMP_DIR_OR_ASM... [--match REGEX] [--list] [--no-loops] [--blocks] [--json OUT]

For every kernel: SIMD width, GRF mode (128 / 256), instruction counts by class, send bytes, spills and fills,
and the loops (back edges in the block graph) with instructions per iteration. Static counts: every instruction of
the program once; loops counted once per iteration. predict.py turns them into dynamic counts with trip counts.

Classes (see classify()):
  send.load.global / send.store.global   (load.ugm / store.ugm; 'block' = SIMD1 transposed dxNt, 'lane' = per lane)
  send.load.slm / send.store.slm / send.atomic / send.spill / send.fill / send.fence / send.barrier / send.eot
  alu.fp32, alu.fp16, alu.fp64 (any df operand), alu.int, alu.int64 (q / uq), alu.dpas
  math.<fn> (math pipe: inv, sqrt, rsqt, exp, log, invm, rsqtm, ...), alu.madm (IEEE div / sqrt macro steps)
  move.plain / move.convert / move.indirect / move.strided / move.broadcast / move.scalar / move.fp64
  sync.nop / sync.allrd / sync.allwr / sync.bar / sync.other
  ctrl.jmpi / ctrl.goto / ctrl.join / ctrl.<other>
The library entry points (parse_asm, load_dir, Kernel) are used by predict.py.
"""
import argparse, collections, glob, json, os, re, subprocess, sys
from dataclasses import dataclass, field

TYPE_BITS = {"df": 64, "q": 64, "uq": 64, "f": 32, "d": 32, "ud": 32, "hf": 16, "bf": 16, "w": 16, "uw": 16,
             "b": 8, "ub": 8, "tf32": 32, "bf8": 8, "hf8": 8, "v": 16, "uv": 16, "vf": 32}
CTRL = {"jmpi", "goto", "join", "if", "else", "endif", "while", "break", "cont", "call", "calla", "ret", "brc",
        "brd", "halt", "goto.b"}
INT_OPS = {"and", "or", "xor", "not", "shl", "shr", "asr", "rol", "ror", "bfn", "add3", "cbit", "fbl", "fbh", "lzd",
           "bfi1", "bfi2", "bfe", "bfrev", "mach", "macl", "avg", "addc", "subb", "dp4a", "srnd"}
RE_EXEC = re.compile(r"\((\d+)\|M(\d+)\)")
RE_TYPE = re.compile(r":(df|uq|q|f|ud|d|hf|bf|uw|w|ub|b|tf32|vf|uv|v)\b")
RE_SWSB = re.compile(r"\{([^{}]*)\}\s*$")
RE_BLOCK = re.compile(r"^// B(\d+):\s*(\[[^\]]*\],)?\s*Preds:\{([^}]*)\},\s*Succs:\{([^}]*)\}")
RE_DATA = re.compile(r"\.d(8|16|32|64)(u32)?(?:x(\d+))?(t)?\b")


@dataclass
class Inst:
    idx: int
    block: int
    op: str
    pred: str
    wmask: bool
    exec_size: int
    types: list
    pipe: str
    cls: str
    bytes: int = 0
    swsb: str = ""
    sync_toks: tuple = ()
    text: str = ""

    @property
    def bits(self):
        return max([TYPE_BITS.get(t, 32) for t in self.types] or [32])


@dataclass
class Loop:
    header: int        # block id
    latch: int         # block id of the last back edge into the header
    first: int         # first instruction index of the body
    last: int          # last instruction index of the body (inclusive)
    depth: int = 1
    parent: int = -1   # index into Kernel.loops
    kind: str = ""     # 'uniform' (jmpi back edge) or 'simd' (goto / while back edge)


@dataclass
class Kernel:
    path: str
    mangled: str
    name: str            # demangled, shortened
    simd: int
    grf: int
    inst_count: int      # IGC's own count (//.instCount)
    spill_bytes: int
    spill_stores: int
    spill_fills: int
    flag_spills: int
    insts: list = field(default_factory=list)
    loops: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)  # IGC's tail statistics

    def counts(self, first=0, last=None, key="cls"):
        c = collections.Counter()
        for i in self.insts[first:(len(self.insts) if last is None else last + 1)]:
            c[getattr(i, key)] += 1
        return c

    def send_bytes(self, first=0, last=None):
        c = collections.Counter()
        for i in self.insts[first:(len(self.insts) if last is None else last + 1)]:
            if i.bytes:
                c[i.cls] += i.bytes
        return c


def demangle(m):
    try:
        out = subprocess.run(["c++filt"], input=m, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return m
    return out or m


def _targs(s, i):
    """Balanced template argument text starting at s[i] == '<'."""
    d, j = 0, i
    while j < len(s):
        if s[j] == "<":
            d += 1
        elif s[j] == ">":
            d -= 1
            if d == 0:
                return s[i + 1:j]
        j += 1
    return s[i + 1:]


def short_name(dm):
    """Strip SYCL / lambda boilerplate from a demangled kernel name; keep the kernel functor's type."""
    return re.sub(r"\s+", " ", _short_name(dm)).strip()


def _short_name(dm):
    s = dm.replace("typeinfo name for ", "").replace("sycl::_V1::", "").replace("ops41sycl::", "")
    for key in ("operator()<", "launch_routed<", "rows_launch<", "launch<", "run_shape<", "run_q6<"):
        i = s.rfind(key) if key == "operator()<" else s.find(key)
        if i >= 0:
            t = _targs(s, i + len(key) - 1)
            if key == "rows_launch<":
                wg, _, t = t.partition(", ")
                return f"{t} @wg{wg.rstrip('ul')}"
            if key in ("run_shape<", "run_q6<"):
                return f"{key[:-1]}<{t}>"
            return t
    m = re.match(r"([A-Za-z_]\w*)<", s)
    if m:  # a launch helper template: helper<WG, SLM, LT, K>(...) -> "K @wgWG"
        parts, d, cur = [], 0, ""
        for ch in _targs(s, m.end() - 1):
            if ch == "," and d == 0:
                parts.append(cur.strip()); cur = ""
                continue
            d += (ch == "<") - (ch == ">")
            cur += ch
        parts.append(cur.strip())
        nums = [p_ for p_ in parts if re.fullmatch(r"\d+u?l?", p_)]
        rest = [p_ for p_ in parts if not re.fullmatch(r"\d+u?l?", p_) and p_ not in ("float", "unsigned int", "int")]
        if rest:
            return rest[-1] + (f" @wg{nums[0].rstrip('ul')}" if nums else "")
    m = re.search(r"\{lambda\(([^)]*)\)#\d+\}", s)
    if m and m.group(1).split(",")[0].strip() not in ("", "nd_item<1>", "handler&", "int", "auto:1"):
        return "lambda(" + m.group(1).split(",")[0].strip() + ")"
    return s[:200]


def classify(op, text, types, pipe, exec_size, comment):
    base = op.split(".")[0]
    if base in ("load", "store", "atomic", "send", "sendc", "sends", "sendsc") or op.startswith("load_block2d") \
            or op.startswith("store_block2d"):
        if "spill to" in comment:
            return "send.spill"
        if "fill from" in comment:
            return "send.fill"
        if "EOT" in text:
            return "send.eot"
        if base == "atomic":
            return "send.atomic"
        if op.startswith("send"):
            if "fence" in comment:
                return "send.fence"
            if "gtwy" in op:
                return "send.barrier"
            return "send.other"
        space = "slm" if ".slm" in op else "global" if (".ugm" in op or "block2d" in op) else \
            "typed" if ".tgm" in op else "other"
        return f"send.{base}.{space}"
    if op.startswith("math"):
        return "math." + (op.split(".", 1)[1] if "." in op else "?")
    if base in CTRL or op in CTRL:
        return "ctrl." + base
    if base == "sync":
        k = op.split(".", 1)[1] if "." in op else "?"
        return "sync." + (k if k in ("nop", "allrd", "allwr", "bar") else "other")
    if base == "nop":
        return "sync.nop"
    if base in ("mov", "movi"):
        if "[a0" in text or base == "movi":
            return "move.indirect"
        if "df" in types:
            return "move.fp64"
        real = [t for t in types[:2] if t not in ("v", "uv", "vf")]
        norm = {"ud": "d", "uw": "w", "ub": "b", "uq": "q"}
        if len(set(norm.get(t, t) for t in real)) > 1:
            return "move.convert"
        if exec_size == 1:
            return "move.scalar"
        if re.search(r"<0;1,0>", text):
            return "move.broadcast"
        if re.search(r"r\d+\.\d+<([2-9]|\d\d)>:", text) or \
                any((v, w, h) != ("1", "1", "0") and not (v == w and h == "1")
                    for v, w, h in re.findall(r"<(\d+);(\d+),(\d+)>", text)):
            return "move.strided"
        return "move.plain"
    if base == "madm":
        return "alu.madm"
    if base == "dpas" or base == "dpasw":
        return "alu.dpas"
    if "df" in types:
        return "alu.fp64"
    if pipe == "math":
        return "math.?"
    fl = [t for t in types if t in ("f", "hf", "bf", "tf32", "vf")]
    if fl and base not in INT_OPS:
        return "alu.fp16" if all(t in ("hf", "bf") for t in fl) else "alu.fp32"
    if "q" in types or "uq" in types:
        return "alu.int64"
    return "alu.int"


def parse_asm(path, want_name=True):
    lines = open(path, errors="replace").read().split("\n")
    mangled, grf, icount, spill_b = "", 128, 0, 0
    flag_sp = 0
    stats = {}
    insts, blocks = [], {}
    order = []          # block ids in layout order
    cur_block = -1
    m = re.search(r"simd(\d+)", os.path.basename(path))
    simd_file = int(m.group(1)) if m else 0
    for ln in lines:
        if ln.startswith("//"):
            if ln.startswith("//.kernel "):
                mangled = ln.split(None, 1)[1].strip()
            elif ln.startswith("//.thread_config"):
                g = re.search(r"numGRF=(\d+)", ln)
                grf = int(g.group(1)) if g else grf
            elif ln.startswith("//.instCount"):
                icount = int(ln.split()[1])
            elif ln.startswith("//.spill size"):
                spill_b = int(ln.split()[2])
            elif ln.startswith("//.spill flag"):
                flag_sp += int(ln.split()[-1])
            elif ln.startswith("// B"):
                b = RE_BLOCK.match(ln)
                if b:
                    bid = int(b.group(1))
                    succs = [int(x.strip()[1:]) for x in b.group(4).split(",") if x.strip().startswith("B")]
                    blocks[bid] = {"succs": succs, "first": len(insts), "div": bool(b.group(2))}
                    order.append(bid)
                    cur_block = bid
            elif re.match(r"^//\.\w+: ", ln):
                k, v = ln[3:].split(":", 1)
                try:
                    stats[k] = int(v.strip())
                except ValueError:
                    pass
            continue
        s = ln.strip()
        if not s or s.endswith(":") and " " not in s:
            continue
        code, _, comment = s.partition("//")
        code = code.strip()
        if not code:
            continue
        pred = ""
        if code.startswith("("):
            j = code.index(")")
            pred, code = code[1:j], code[j + 1:].strip()
        op = code.split(None, 1)[0]
        e = RE_EXEC.search(code)
        exec_size = int(e.group(1)) if e else 1
        types = RE_TYPE.findall(code)
        pm = re.search(r"ALU pipe: (\w+)", comment)
        pipe = pm.group(1) if pm else ""
        cls = classify(op, code, types, pipe, exec_size, comment)
        if not pipe:
            pipe = "send" if cls.startswith("send") else "ctrl" if cls.startswith("ctrl") else \
                "sync" if cls.startswith("sync") else "math" if cls.startswith("math") else "int"
        nbytes = 0
        if cls.startswith("send.") and cls not in ("send.barrier", "send.eot", "send.fence", "send.other"):
            d = RE_DATA.search(op)
            if d:
                eb = int(d.group(1)) // 8
                vec = int(d.group(3) or 1)
                nbytes = eb * vec if d.group(4) else eb * vec * exec_size
        sw = RE_SWSB.search(code)
        toks = tuple(int(t) for t in re.findall(r"\$(\d+)", code.split("//")[0])) if op.startswith("sync.all") else ()
        insts.append(Inst(len(insts), cur_block, op, pred, pred.startswith("W"), exec_size, types, pipe, cls, nbytes,
                          sw.group(1) if sw else "", toks, s if len(s) < 400 else s[:400]))
    # block ranges
    for n, bid in enumerate(order):
        blocks[bid]["last"] = (blocks[order[n + 1]]["first"] - 1) if n + 1 < len(order) else len(insts) - 1
    # loops: back edges (successor laid out at or before the block)
    pos = {b: n for n, b in enumerate(order)}
    heads = {}
    for b in order:
        for s_ in blocks[b]["succs"]:
            if s_ in pos and pos[s_] <= pos[b]:
                if s_ not in heads or pos[b] > pos[heads[s_]]:
                    heads[s_] = b
    loops = []
    for h, l in sorted(heads.items(), key=lambda x: pos[x[0]]):
        first, last = blocks[h]["first"], blocks[l]["last"]
        if last < first:
            continue
        tail_ops = [insts[i].op for i in range(max(first, last - 3), last + 1)]
        kind = "uniform" if any(o == "jmpi" for o in tail_ops) else "simd"
        loops.append(Loop(h, l, first, last, kind=kind))
    for i, L in enumerate(loops):
        enc = [j for j, M in enumerate(loops) if j != i and M.first <= L.first and L.last <= M.last
               and (M.first, -M.last) != (L.first, -L.last)]
        if enc:
            L.parent = max(enc, key=lambda j: loops[j].first)
            L.depth = 1 + len(enc)
    simd = simd_file or max([i.exec_size for i in insts if not i.wmask] or [16])
    k = Kernel(path, mangled, "", simd, grf, icount, spill_b,
               sum(1 for i in insts if i.cls == "send.spill"), sum(1 for i in insts if i.cls == "send.fill"),
               flag_sp, insts, loops, stats)
    if want_name and mangled:
        k.name = short_name(demangle(mangled))
    return k


def asm_files(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            out += sorted(glob.glob(os.path.join(p, "*.asm")))
        else:
            out += sorted(glob.glob(p)) or [p]
    return out


def load_dir(paths, match=None):
    """All kernels in the dump directories / files; match = regex on the short demangled name."""
    files = asm_files(paths if isinstance(paths, (list, tuple)) else [paths])
    heads = []
    for f in files:
        with open(f, errors="replace") as fh:
            first = fh.readline()
        mg = first.split(None, 1)[1].strip() if first.startswith("//.kernel") else ""
        heads.append((f, mg))
    # one c++filt call for all names
    try:
        dm = subprocess.run(["c++filt"], input="\n".join(h[1] for h in heads), capture_output=True, text=True,
                            timeout=60).stdout.split("\n")
    except Exception:
        dm = [h[1] for h in heads]
    ks = []
    for (f, mg), d in zip(heads, dm):
        nm = short_name(d) if mg else os.path.basename(f)
        if nm.startswith(("RoundedRangeKernel", "handler::fill", "fill<", "Intel_Symbol_Table_Void_Program")) \
                or "handler::fill" in d:
            continue
        if match and not re.search(match, nm):
            continue
        k = parse_asm(f, want_name=False)
        k.name = nm
        ks.append(k)
    return ks


GROUPS = [("sends", "send."), ("fp32", "alu.fp32"), ("fp16", "alu.fp16"), ("fp64", "alu.fp64"),
          ("madm", "alu.madm"), ("math", "math."), ("int", "alu.int"), ("moves", "move."), ("sync", "sync."),
          ("ctrl", "ctrl.")]


def group_counts(c):
    g = collections.Counter()
    for k, v in c.items():
        for name, pre in GROUPS:
            if k.startswith(pre):
                g[name] += v
                break
        else:
            g["other"] += v
    return g


def summary(k, show_loops=True):
    c = k.counts()
    g = group_counts(c)
    pipes = k.counts(key="pipe")
    sb = k.send_bytes()
    out = [f"== {k.name}", f"   file {os.path.basename(k.path)}  SIMD{k.simd}  GRF {k.grf}  instructions {len(k.insts)}"
           f" (IGC {k.inst_count})  spill {k.spill_bytes} B: {k.spill_stores} stores / {k.spill_fills} fills,"
           f" flag spills {k.flag_spills}"]
    out.append("   groups: " + "  ".join(f"{n} {g[n]}" for n, _ in GROUPS if g[n]) +
               ("  other %d" % g["other"] if g["other"] else ""))
    out.append("   pipes:  " + "  ".join(f"{p} {n}" for p, n in sorted(pipes.items(), key=lambda x: -x[1])))
    det = [f"{cl} {n}" for cl, n in sorted(c.items()) if cl.startswith(("send.", "move.", "math.", "sync.", "ctrl."))
           or cl in ("alu.fp64", "alu.madm", "alu.int64", "alu.dpas")]
    out.append("   detail: " + "  ".join(det))
    if sb:
        out.append("   send bytes (static, per thread): " + "  ".join(f"{cl} {b}" for cl, b in sorted(sb.items())))
    if show_loops:
        for n, L in enumerate(k.loops):
            lc = group_counts(k.counts(L.first, L.last))
            lb = k.send_bytes(L.first, L.last)
            out.append(f"   loop L{n} depth {L.depth}{' in L%d' % L.parent if L.parent >= 0 else ''} ({L.kind},"
                       f" B{L.header:03d}-B{L.latch:03d}): {L.last - L.first + 1} instructions per iteration: " +
                       "  ".join(f"{nm} {lc[nm]}" for nm, _ in GROUPS if lc[nm]) +
                       (f"; bytes {sum(lb.values())}" if lb else ""))
    return "\n".join(out)


def block_map(k):
    """One line per basic block: instruction range, class groups, bytes, branch at its end."""
    by = collections.OrderedDict()
    for i in k.insts:
        by.setdefault(i.block, []).append(i)
    inloop = collections.defaultdict(list)
    for n, L in enumerate(k.loops):
        for i in range(L.first, L.last + 1):
            inloop[k.insts[i].block].append(n)
    out = []
    for b, ins in by.items():
        g = group_counts(collections.Counter(i.cls for i in ins))
        nb = sum(i.bytes for i in ins)
        tail = ins[-1]
        br = ""
        if tail.cls.startswith("ctrl."):
            tgt = re.findall(r"\b(_\w+|L\d+)\b", tail.text.split("//")[0])
            br = f" -> {tail.op}{'(' + tail.pred + ')' if tail.pred and tail.pred != 'W' else ''} {' '.join(tgt[:2])}"
        loops = sorted(set(inloop.get(b, [])))
        out.append(f"  B{b:03d} i{ins[0].idx}-{ins[-1].idx} n{len(ins):5d} "
                   + " ".join(f"{nm}{g[nm]}" for nm, _ in GROUPS if g[nm])
                   + (f" bytes{nb}" if nb else "") + (f" loops{loops}" if loops else "") + br)
    return "\n".join(out)


def to_json(k):
    c = k.counts()
    return {"name": k.name, "mangled": k.mangled, "file": k.path, "simd": k.simd, "grf": k.grf,
            "instructions": len(k.insts), "igc_inst_count": k.inst_count, "spill_bytes": k.spill_bytes,
            "spill_stores": k.spill_stores, "spill_fills": k.spill_fills, "flag_spills": k.flag_spills,
            "classes": dict(c), "groups": dict(group_counts(c)), "pipes": dict(k.counts(key="pipe")),
            "send_bytes": dict(k.send_bytes()),
            "loops": [{"id": n, "header": L.header, "latch": L.latch, "depth": L.depth, "parent": L.parent,
                       "kind": L.kind, "instructions": L.last - L.first + 1,
                       "groups": dict(group_counts(k.counts(L.first, L.last))),
                       "classes": dict(k.counts(L.first, L.last)), "send_bytes": dict(k.send_bytes(L.first, L.last))}
                      for n, L in enumerate(k.loops)]}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="dump directories or .asm files")
    ap.add_argument("--match", help="regex on the short kernel name")
    ap.add_argument("--list", action="store_true", help="one line per kernel")
    ap.add_argument("--no-loops", action="store_true")
    ap.add_argument("--blocks", action="store_true", help="per basic block map (for predict.py --skip)")
    ap.add_argument("--json", help="write the census as JSON")
    a = ap.parse_args()
    ks = load_dir(a.paths, a.match)
    if a.list:
        for k in ks:
            g = group_counts(k.counts())
            print(f"{os.path.basename(k.path)[-22:-4]}  SIMD{k.simd} GRF{k.grf:3d} n{len(k.insts):6d} sp{k.spill_bytes:5d} "
                  f"loops {len(k.loops):2d} sends {g['sends']:5d} fp64 {g['fp64']:5d}  {k.name[:150]}")
    else:
        for k in ks:
            print(summary(k, not a.no_loops))
            if a.blocks:
                print(block_map(k))
    if a.json:
        json.dump([to_json(k) for k in ks], open(a.json, "w"), indent=1)
        print(f"wrote {a.json} ({len(ks)} kernels)", file=sys.stderr)


if __name__ == "__main__":
    main()
