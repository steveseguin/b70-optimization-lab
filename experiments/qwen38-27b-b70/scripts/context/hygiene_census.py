#!/usr/bin/env python3
"""Context hygiene census: how much of an agent's context deterministic,
information-preserving rules could remove, measured with the served model's
tokenizer (Qwen3.8 27B).

Streams each transcript line by line (bounded memory), rebuilds the context as
an append-only list of segments, and measures rules R1..R6 (see the note
experiments/qwen38-27b-b70/notes/2026-10-05-context-hygiene-census.md).

Prints only aggregate numbers (JSON) -- never transcript text.

Usage:
  hygiene_census.py claude FILE.jsonl [FILE.jsonl ...]
  hygiene_census.py snapshots DIR [DIR ...]      # dirs holding context_snapshots/turn-*.json
"""
import json
import re
import sys
import glob
import os
import statistics
from array import array

from tokenizers import Tokenizer

TOKENIZER = "/mnt/fast-ai/llm-models/qwen3.8-27b-fp8/tokenizer.json"
TOK = Tokenizer.from_file(TOKENIZER)

LOOKBACK = 131072          # dedup referents must lie within this many raw tokens
R1_PTR = 12
R2_PTR = 12
R3_PTR = 6
R6_LIMIT, R6_HEAD, R6_TAIL, R6_PTR = 2000, 400, 400, 20
WINDOWS = (32768, 131072)
BIG = 1 << 60


def ntok(s):
    if not s:
        return 0
    if len(s) <= 120000:
        return len(TOK.encode(s, add_special_tokens=False).ids)
    n, i = 0, 0
    while i < len(s):
        j = s.find("\n", i + 100000)
        j = len(s) if j < 0 else j + 1
        n += len(TOK.encode(s[i:j], add_special_tokens=False).ids)
        i = j
    return n


# ---------------------------------------------------------------- R5
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[@-Z\\-_]")
SEP = re.compile(r"([-=_*#~.+─━═│┃▀▄█░▒▓·•])\1{9,}")
BLANKS = re.compile(r"\n{4,}")   # 3+ blank lines


def r5_norm(s):
    s = ANSI.sub("", s)
    if "\r" in s:
        out = []
        for ln in s.split("\n"):
            if ln.endswith("\r"):
                ln = ln[:-1]
            if "\r" in ln:
                parts = [p for p in ln.split("\r") if p]
                ln = parts[-1] if parts else ""
            out.append(ln)
        s = "\n".join(out)
    s = "\n".join(ln.rstrip() for ln in s.split("\n"))
    s = BLANKS.sub("\n\n", s)
    s = SEP.sub(lambda m: m.group(1) * 4, s)
    return s


# ---------------------------------------------------------------- R3
def r3_apply(text, seen, cur_pos, rawpos, min_len=40):
    """Remove lines (>= min_len chars) already present verbatim in an earlier
    kept output within LOOKBACK. Returns (kept_text, runs, min_ref)."""
    lines = text.split("\n")
    kept, runs, in_run, min_ref = [], 0, False, BIG
    for ln in lines:
        rep = False
        if len(ln) >= min_len:
            ref = seen.get(hash(ln))
            if ref is not None and rawpos[ref] >= cur_pos - LOOKBACK:
                rep = True
                if ref < min_ref:
                    min_ref = ref
        if rep:
            if not in_run:
                runs += 1
                in_run = True
        else:
            in_run = False
            kept.append(ln)
    return "\n".join(kept), runs, (min_ref if min_ref != BIG else -1)


def r3_register(text, seen, idx, min_len=40, removed_text=None):
    for ln in text.split("\n"):
        if len(ln) >= min_len:
            seen[hash(ln)] = idx


def prune(d, rawpos, cur_pos):
    lim = cur_pos - LOOKBACK
    return {k: v for k, v in d.items() if rawpos[v] >= lim}


READ_CMD = re.compile(r"^\s*(cat|head|tail|nl|sed\s+-n\s+\S+)(\s+-\S+)*\s+[^|;&<>`$()]+$")


def line_set(text):
    return frozenset(hash(ln) for ln in text.split("\n") if ln.strip())


def pct(a, b):
    return round(100.0 * a / b, 2) if b else 0.0


def quantiles(v):
    if not v:
        return {}
    v = sorted(v)
    q = lambda p: v[min(len(v) - 1, int(p * len(v)))]
    return {"n": len(v), "p50": q(0.5), "p90": q(0.9), "p99": q(0.99), "max": v[-1],
            "mean": round(sum(v) / len(v), 1)}


# ---------------------------------------------------------------- transcript
class Census:
    def __init__(self):
        # per-segment arrays
        self.kind = []                       # small str
        self.raw = array("q")
        self.rawpos = array("q")             # raw stream position at segment start
        self.turn = array("q")
        self.r1 = array("q"); self.r3 = array("q"); self.r5 = array("q"); self.r6 = array("q")
        self.sup_alone = array("q")          # R2 alone: superseding segment index
        # combined lossless (R5 -> R2 -> R1 -> R3)
        self.L = array("q"); self.Lfb = array("q"); self.Lref = array("q"); self.Lsup = array("q")
        self.L6 = array("q"); self.L6fb = array("q")
        self.pos = 0
        self.cur_turn = 0
        self.seen_uuid = set()
        self.tool_uses = {}                  # id -> is_read
        # dedup dicts
        self.r1_raw, self.r1_norm = {}, {}
        self.r3_raw, self.r3_norm = {}, {}
        self.pending_alone, self.pending_comb = [], []   # (idx, lineset)
        # R6 reference proxy
        self.r6_index = {}                   # hash(prefix30) -> list[(len, hash(full), out_id)]
        self.r6_outputs = []                 # [seg_idx, referenced_by_text, referenced_by_call, first_ref_seg]
        self.r6_mid_tokens = 0
        self.images = 0
        self.pending_wide = []               # informational R2-wide: any output (>=3 lines)
        self.wide_saved = 0
        self.wide_n = 0
        self.call_seen = {}                  # informational: repeated lines in tool-call inputs
        self.call_rep_saved = 0
        self.compactions = 0
        self.tool_out_sizes = []
        self.r5_before = self.r5_after = 0

    # -- generic segment
    def add(self, kind, text, extra=None):
        n = ntok(text)
        idx = len(self.raw)
        self.kind.append(kind)
        self.raw.append(n)
        self.rawpos.append(self.pos)
        self.turn.append(self.cur_turn)
        e = extra or {}
        self.r1.append(e.get("r1", n)); self.r3.append(e.get("r3", n))
        self.r5.append(e.get("r5", n)); self.r6.append(e.get("r6", n))
        self.sup_alone.append(BIG)
        self.L.append(e.get("L", n)); self.Lfb.append(e.get("Lfb", n))
        self.Lref.append(e.get("Lref", -1)); self.Lsup.append(BIG)
        self.L6.append(e.get("L6", n)); self.L6fb.append(e.get("L6fb", n))
        self.pos += n
        if idx and idx % 3000 == 0:
            for name in ("r1_raw", "r1_norm", "r3_raw", "r3_norm", "call_seen"):
                setattr(self, name, prune(getattr(self, name), self.rawpos, self.pos))
            lim = self.pos - LOOKBACK
            self.pending_alone = [p for p in self.pending_alone if self.rawpos[p[0]] >= lim]
            self.pending_comb = [p for p in self.pending_comb if self.rawpos[p[0]] >= lim]
            self.pending_wide = [p for p in self.pending_wide if self.rawpos[p[0]] >= lim]
        return idx, n

    def scan_refs(self, text, idx, is_call):
        """R6 proxy: does this later assistant text / tool call quote a
        distinctive line from a truncated middle?"""
        if not self.r6_index or len(text) < 30:
            return
        idxd = self.r6_index
        for i in range(len(text) - 29):
            c = idxd.get(hash(text[i:i + 30]))
            if c is None:
                continue
            for (ln, hf, oid) in c:
                if hash(text[i:i + ln]) == hf:
                    rec = self.r6_outputs[oid]
                    if is_call:
                        rec[2] = True
                    else:
                        rec[1] = True
                    if rec[3] < 0:
                        rec[3] = idx

    # -- tool output with all rules
    def add_tool_output(self, text, is_read):
        idx = len(self.raw)
        pos = self.pos
        n = ntok(text)
        self.tool_out_sizes.append(n)
        lim = pos - LOOKBACK
        # R6 reference index (raw text; before this output's lines are registered)
        if n > R6_LIMIT:
            self.index_r6_middle(text, n)

        # R1 alone
        h = hash(text)
        ref = self.r1_raw.get(h)
        r1 = R1_PTR if (ref is not None and self.rawpos[ref] >= lim and n > R1_PTR) else n
        if r1 == n:
            self.r1_raw[h] = idx
        # R3 alone
        kept, runs, _ = r3_apply(text, self.r3_raw, pos, self.rawpos)
        r3 = min(n, ntok(kept) + R3_PTR * runs) if runs else n
        r3_register(text, self.r3_raw, idx)
        # R5 alone
        norm = r5_norm(text)
        nn = ntok(norm) if norm != text else n
        self.r5_before += n; self.r5_after += nn
        # R6 alone
        r6 = (R6_HEAD + R6_TAIL + R6_PTR) if n > R6_LIMIT else n

        # R2 alone: does this output contain an earlier pending read?
        ls = line_set(text) if text.strip() else frozenset()
        if ls:
            still = []
            for (j, s) in self.pending_alone:
                if s <= ls:
                    self.sup_alone[j] = idx
                else:
                    still.append((j, s))
            self.pending_alone = still
            still = []
            for (j, s) in self.pending_wide:
                if s <= ls:
                    if self.raw[j] > R2_PTR:
                        self.wide_saved += self.raw[j] - R2_PTR
                        self.wide_n += 1
                else:
                    still.append((j, s))
            self.pending_wide = still

        # ---- combined lossless: R5 -> R2 superseder? -> R1 -> R3
        # An identical re-print becomes an R1 pointer and supersedes nothing
        # (otherwise both copies would be pointers). A non-identical output
        # that contains an earlier read is kept in full and the read becomes
        # an R2 pointer.
        hn = hash(norm)
        lsn = line_set(norm) if norm.strip() else frozenset()
        ref = self.r1_norm.get(hn)
        is_dup = ref is not None and self.rawpos[ref] >= lim and nn > R1_PTR
        supersedes = []
        if lsn and not is_dup:
            still = []
            for (j, s) in self.pending_comb:
                if s <= lsn:
                    supersedes.append(j)
                else:
                    still.append((j, s))
            self.pending_comb = still
        if is_dup:
            L, Lfb, Lref = R1_PTR, nn, ref
        elif supersedes:
            for j in supersedes:
                self.Lsup[j] = idx
            L = Lfb = nn
            Lref = -1
            self.r1_norm[hn] = idx
            r3_register(norm, self.r3_norm, idx)
        else:
            if True:
                self.r1_norm[hn] = idx
                keptn, runsn, ref3 = r3_apply(norm, self.r3_norm, pos, self.rawpos)
                if runsn:
                    L = min(nn, ntok(keptn) + R3_PTR * runsn)
                    Lref = ref3 if L < nn else -1
                else:
                    L, Lref = nn, -1
                Lfb = nn
                # register only lines kept verbatim
                r3_register(keptn if runsn else norm, self.r3_norm, idx)
        r6f = lambda x: (R6_HEAD + R6_TAIL + R6_PTR) if x > R6_LIMIT else x
        L6, L6fb = r6f(L), r6f(Lfb)

        idx2, _ = self.add("tool_output", "", None)  # placeholder, fix below
        assert idx2 == idx
        self.raw[idx] = n; self.pos += n
        self.r1[idx] = r1; self.r3[idx] = r3; self.r5[idx] = nn; self.r6[idx] = r6
        self.L[idx] = L; self.Lfb[idx] = Lfb; self.Lref[idx] = Lref
        self.L6[idx] = L6; self.L6fb[idx] = L6fb

        if ls and len(ls) >= 3:
            self.pending_wide.append((idx, ls))
        if is_read and ls and len(ls) >= 3:
            self.pending_alone.append((idx, ls))
            if not is_dup and lsn:
                self.pending_comb.append((idx, lsn))

    def index_r6_middle(self, text, n):
        head_enc = TOK.encode(text[:20000], add_special_tokens=False)
        hc = head_enc.offsets[R6_HEAD - 1][1] if len(head_enc.ids) >= R6_HEAD else len(text)
        tail_src = text[-20000:]
        tail_enc = TOK.encode(tail_src, add_special_tokens=False)
        if len(tail_enc.ids) >= R6_TAIL:
            tc = len(text) - len(tail_src) + tail_enc.offsets[-R6_TAIL][0]
        else:
            tc = len(text) - len(tail_src)
        if tc <= hc:
            return
        middle = text[hc:tc]
        self.r6_mid_tokens += n - R6_HEAD - R6_TAIL
        edge = set(ln.strip() for ln in (text[:hc] + "\n" + text[tc:]).split("\n"))
        oid = len(self.r6_outputs)
        self.r6_outputs.append([len(self.raw), False, False, -1])
        added = 0
        for ln in middle.split("\n"):
            s = ln.strip()
            if len(s) < 30 or s in edge:
                continue
            if len(ln) >= 40 and hash(ln) in self.r3_raw:
                continue   # also present in an earlier output: not distinctive
            self.r6_index.setdefault(hash(s[:30]), []).append((len(s), hash(s), oid))
            added += 1
            if added >= 4000:
                break


def process_claude(path):
    c = Census()
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:
                continue
            t = r.get("type")
            if t not in ("user", "assistant"):
                continue
            if r.get("isCompactSummary"):
                c.compactions += 1
                continue
            u = r.get("uuid")
            if u:
                if u in c.seen_uuid:
                    continue
                c.seen_uuid.add(u)
            m = r.get("message")
            if not isinstance(m, dict):
                continue
            content = m.get("content")
            meta = bool(r.get("isMeta"))
            if t == "user":
                if isinstance(content, str):
                    if not meta:
                        c.cur_turn += 1
                    c.add("injected" if meta else "user_text", content)
                    continue
                if not isinstance(content, list):
                    continue
                for b in content:
                    bt = b.get("type")
                    if bt == "text":
                        if not meta:
                            c.cur_turn += 1
                        c.add("injected" if meta else "user_text", b.get("text", ""))
                    elif bt == "tool_result":
                        cc = b.get("content")
                        if isinstance(cc, list):
                            parts = []
                            for x in cc:
                                if x.get("type") == "text":
                                    parts.append(x.get("text", ""))
                                else:
                                    c.images += 1
                            cc = "\n".join(parts)
                        if not isinstance(cc, str):
                            cc = ""
                        is_read = c.tool_uses.pop(b.get("tool_use_id"), False)
                        c.add_tool_output(cc, is_read)
            else:
                if not isinstance(content, list):
                    continue
                for b in content:
                    bt = b.get("type")
                    if bt == "text":
                        txt = b.get("text", "")
                        idx, _ = c.add("assistant_text", txt)
                        c.scan_refs(txt, idx, False)
                    elif bt == "thinking":
                        c.add("thinking", b.get("thinking", ""))
                    elif bt == "tool_use":
                        name = b.get("name", "")
                        inp = b.get("input", {})
                        txt = name + " " + json.dumps(inp, ensure_ascii=False)
                        is_read = name == "Read" or (
                            name == "Bash" and isinstance(inp, dict)
                            and bool(READ_CMD.match(str(inp.get("command", "")))))
                        c.tool_uses[b.get("id")] = is_read
                        idx, n = c.add("tool_call", txt)
                        kept, runs, _ = r3_apply(txt, c.call_seen, c.rawpos[idx], c.rawpos)
                        if runs:
                            c.call_rep_saved += max(0, n - ntok(kept) - R3_PTR * runs)
                        r3_register(txt, c.call_seen, idx)
                        scan = json.dumps(inp, ensure_ascii=False) if not isinstance(inp, dict) else \
                            "\n".join(str(v) for v in inp.values())
                        c.scan_refs(scan, idx, True)
    return summarise(c, os.path.basename(path))


# ---------------------------------------------------------------- windows
def seg_size(c, s, t, start, variant):
    """Processed size of segment s at time t given window start (for refs)."""
    k = c.kind[s]
    if variant >= 1 and k == "thinking" and c.turn[s] != c.turn[t]:
        return 0
    if k != "tool_output":
        return c.raw[s]
    if c.Lsup[s] <= t:
        return R2_PTR
    ok = c.Lref[s] < 0 or c.Lref[s] >= start
    if variant == 2:
        return c.L6[s] if ok else c.L6fb[s]
    return c.L[s] if ok else c.Lfb[s]


def window_raw(c, t, W, variant):
    start = 0
    for _ in range(8):
        acc = 0
        s = t
        while s >= 0:
            sz = seg_size(c, s, t, start, variant)
            if acc + sz >= W:
                break
            acc += sz
            s -= 1
        if s < 0:
            return None                      # window not full yet
        new_start = s
        if new_start == start:
            break
        start = new_start
    # raw held: full segments after s plus fraction of s
    raw_held = 0
    for j in range(s + 1, t + 1):
        raw_held += c.raw[j]
    sz = seg_size(c, s, t, start, variant)
    if sz > 0:
        raw_held += c.raw[s] * (W - acc) / sz
    return raw_held


def multipliers(c, points=1500):
    n = len(c.raw)
    step = max(1, n // points)
    out = {}
    for W in WINDOWS:
        for variant, name in ((0, "lossless_R1235"), (1, "plus_R4"), (2, "plus_R4_R6")):
            vals = []
            for t in range(0, n, step):
                if c.rawpos[t] + c.raw[t] < W:
                    continue
                v = window_raw(c, t, W, variant)
                if v is not None:
                    vals.append(v)
            out[f"{W}/{name}"] = {"points": len(vals),
                                 "mean_raw_held": round(sum(vals) / len(vals)) if vals else None,
                                 "multiplier": round(sum(vals) / len(vals) / W, 3) if vals else None}
    return out


def summarise(c, name):
    total = sum(c.raw)
    comp = {}
    for k, n in zip(c.kind, c.raw):
        comp[k] = comp.get(k, 0) + n
    idx_out = [i for i, k in enumerate(c.kind) if c.kind[i] == "tool_output"]
    sav = lambda arr: sum(c.raw[i] - arr[i] for i in idx_out)
    r2 = sum(c.raw[i] - R2_PTR for i in idx_out if c.sup_alone[i] < BIG and c.raw[i] > R2_PTR)
    last_turn = c.turn[-1] if len(c.turn) else 0
    r4 = sum(n for k, n, tt in zip(c.kind, c.raw, c.turn) if k == "thinking" and tt != last_turn)
    # combined lossless final state
    final_L = 0
    final_L6 = 0
    for i in idx_out:
        if c.Lsup[i] < BIG:
            final_L += R2_PTR; final_L6 += R2_PTR
        else:
            final_L += c.L[i]; final_L6 += c.L6[i]
    out_raw = sum(c.raw[i] for i in idx_out)
    comb_lossless = out_raw - final_L
    comb_all = comb_lossless + r4 + (final_L - final_L6)
    n6 = len(c.r6_outputs)
    ref_any = sum(1 for r in c.r6_outputs if r[1] or r[2])
    ref_call = sum(1 for r in c.r6_outputs if r[2])
    near = sum(1 for r in c.r6_outputs if r[3] >= 0 and r[3] - r[0] <= 6)
    thinking_nonempty = sum(1 for k, n in zip(c.kind, c.raw) if k == "thinking" and n > 0)
    thinking_blocks = sum(1 for k in c.kind if k == "thinking")
    res = {
        "transcript": name[:8],
        "segments": len(c.raw), "total_tokens": total, "compaction_records_skipped": c.compactions,
        "images_skipped": c.images,
        "composition": {k: {"tokens": v, "pct": pct(v, total)} for k, v in sorted(comp.items(), key=lambda x: -x[1])},
        "thinking_blocks": thinking_blocks, "thinking_blocks_with_visible_text": thinking_nonempty,
        "tool_output_sizes": quantiles(c.tool_out_sizes),
        "rules_alone": {
            "R1_exact_dup": {"tokens": sav(c.r1), "pct": pct(sav(c.r1), total)},
            "R2_superseded_reads": {"tokens": r2, "pct": pct(r2, total),
                                    "reads_superseded": sum(1 for i in idx_out if c.sup_alone[i] < BIG)},
            "R3_repeated_lines": {"tokens": sav(c.r3), "pct": pct(sav(c.r3), total)},
            "R4_earlier_thinking": {"tokens": r4, "pct": pct(r4, total)},
            "R5_whitespace_noise": {"tokens": c.r5_before - c.r5_after, "pct": pct(c.r5_before - c.r5_after, total),
                                    "pct_of_tool_output": pct(c.r5_before - c.r5_after, c.r5_before)},
            "R6_moved_to_disk": {"tokens": sav(c.r6), "pct": pct(sav(c.r6), total),
                                 "outputs_truncated": n6,
                                 "outputs_with_later_quote": ref_any,
                                 "outputs_quoted_by_later_tool_call": ref_call,
                                 "outputs_quoted_within_6_segments": near},
        },
        "extra_R2_any_output_contained_later": {"tokens": c.wide_saved, "pct": pct(c.wide_saved, total), "outputs": c.wide_n},
        "extra_R3_on_tool_call_inputs": {"tokens": c.call_rep_saved, "pct": pct(c.call_rep_saved, total)},
        "combined": {
            "lossless_R1235": {"tokens": comb_lossless, "pct": pct(comb_lossless, total)},
            "plus_R4": {"tokens": comb_lossless + r4, "pct": pct(comb_lossless + r4, total)},
            "plus_R4_R6": {"tokens": comb_all, "pct": pct(comb_all, total)},
        },
    }
    res["windows"] = multipliers(c)
    return res


# ---------------------------------------------------------------- data set 2
def process_snapshots(dirs):
    per_trial = []
    all_shares = []
    for d in dirs:
        files = sorted(glob.glob(os.path.join(d, "context_snapshots", "turn-*.json")))
        shares, last_share, max_tokens = [], None, 0
        for f in files:
            with open(f) as fh:
                snap = json.load(fh)
            msgs = snap.get("messages") or []
            ass = [i for i, m in enumerate(msgs) if m.get("role") == "assistant"]
            last_a = ass[-1] if ass else -1
            total = earlier = 0
            for i, m in enumerate(msgs):
                cont = m.get("content")
                if isinstance(cont, list):
                    cont = "\n".join(x.get("text", "") for x in cont if isinstance(x, dict))
                n = 4 + ntok(cont or "")
                if m.get("tool_calls"):
                    n += ntok(json.dumps([tc.get("function", tc) for tc in m["tool_calls"]], ensure_ascii=False))
                rc = m.get("reasoning_content")
                if isinstance(rc, str) and rc:
                    rn = ntok(rc) + 4
                    n += rn
                    if i != last_a:
                        earlier += rn
                total += n
            if total:
                sh = earlier / total
                shares.append(sh)
                last_share = sh
                max_tokens = max(max_tokens, total)
        all_shares += shares
        parts = d.rstrip("/").split("/")
        per_trial.append({"trial": "/".join(parts[-5:-1][-3:]), "calls": len(shares),
                          "median_pct": round(100 * statistics.median(shares), 1) if shares else None,
                          "max_pct": round(100 * max(shares), 1) if shares else None,
                          "final_call_pct": round(100 * last_share, 1) if last_share is not None else None,
                          "max_call_tokens": max_tokens})
    return {"trials": per_trial,
            "all_calls": {"n": len(all_shares),
                          "median_pct": round(100 * statistics.median(all_shares), 1),
                          "max_pct": round(100 * max(all_shares), 1),
                          "median_of_trial_medians": round(statistics.median(
                              [t["median_pct"] for t in per_trial if t["median_pct"] is not None]), 1)}}


def main():
    mode, args = sys.argv[1], sys.argv[2:]
    if mode == "claude":
        for p in args:
            print(json.dumps(process_claude(p)), flush=True)
    elif mode == "snapshots":
        print(json.dumps(process_snapshots(args)), flush=True)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
