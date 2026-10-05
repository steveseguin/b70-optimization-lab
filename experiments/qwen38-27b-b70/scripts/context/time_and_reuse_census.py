#!/usr/bin/env python3
"""Where the wall time of each self-editing trial went, and how much of each prompt the exact prefix cache could reuse.

CPU only, reads existing records, streams one trial at a time (well under 100 MB), prints aggregate tables + JSON.

  time_and_reuse_census.py [--runs DIR ...] [--log SERVER_LOG ...] [--calls] [--json]

Defaults: the second and third self-editing comparisons of 2026-10-05 (ledger 121K, seeds 0/1).
Unfinished trials (no result.json / finished_at) are skipped.

Task A (time). Per call the records carry: server prompt / cached / completion tokens (trajectory.ctx.json step
metrics = the server's usage), the call's wall time (timing.json llm_s) and the tool's wall time (timing.json bash_s).
No streamed token timestamps exist, so the per-call decode rate is NOT measured. Reading time per call is ESTIMATED
from the measured cold-read speeds (832-token pieces) as T832(P) - T832(cached): the time a cold read of the whole
prompt takes minus the time of the cached part. Writing = llm_s - estimated reading (a residual that also holds the
per-call fixed overhead: request, template, scheduling, first step). Other = agent wall - llm - tools (harness, mirror
sync, summaries where the harness does not time them). The server's 10-second engine lines give a second, coarser view:
generated tokens per 10 s in intervals with no prompt reading ("decode-only"), i.e. a 10-s average, not per token.

Task B (reuse). Each call's sent messages (context_snapshots, one per call) are rendered the way the served chat
template renders them (Qwen3.8 template: role tags, <think> kept for every assistant turn unless the harness drops old
thinking, tool calls as <tool_call><function=bash><parameter=command>, tool results as <tool_response> in a user turn;
the tool schema block in the system prompt is left out because it is identical in every call). Common prefixes are
measured in CHARACTERS and converted to tokens with the trial's own per-call ratio (server prompt tokens of that call /
its rendered characters; a prefix covering a whole earlier prompt counts as exactly that prompt's server tokens).
Token figures in Task B are converted, not tokenized (no tokenizer is loaded). The predicted reusable length applies the exact-cache rules (notes/2026-10-05-prefix-cache-reuse-rules.md and
overlays/b70-prefix-cache-exact): 832-token blocks; only prompt blocks are cached; recurrent state kept at the last
block boundary of each prompt and one block before it, at the junction where an attention match outran the kept
states (and one block before), and every 13,312 tokens; with drafting the attention hit drops one block; the hit is the
furthest kept state not beyond that. Eviction is ignored (370K-token pool, one user).
"""
from __future__ import annotations

import bisect
import glob
import json
import os
import re
import sys
import zlib
from datetime import datetime, timezone

BLOCK = 832
RETAIN = 13312
DEFAULT_RUNS = ["/mnt/fast-ai/bench-results/context-clm-second-20261005/client/runs/jobs",
                "/mnt/fast-ai/bench-results/context-clm-third-20261005/client/runs/jobs"]
DEFAULT_LOGS = ["/mnt/fast-ai/bench-results/context-clm-second-20261005/tp2-clm2-w262144/server.log",
                "/mnt/fast-ai/bench-results/context-clm-third-20261005/tp2-clm3-w262144/server.log"]

# Measured single-user speeds (notes/2026-10-05-context-research-results.md and the brief). Rates are whole-prompt
# averages: reading a prompt of L tokens takes L / rate(L). Points marked * are assumptions (see the note).
WRITE = [(8000, 127), (30000, 99), (60000, 70), (120000, 48), (200000, 35), (250000, 26)]
READ832 = [(8000, 2790), (30000, 2600), (60000, 2250), (120000, 1720), (200000, 1330)]   # 8K*, 200K* = 4096-rate x0.85 / x0.76
READ4096 = [(8000, 3280), (30000, 3050), (60000, 2700), (120000, 2190), (200000, 1745), (250000, 1550)]


def interp(table, x):
    if x <= table[0][0]:
        return table[0][1]
    for (x0, y0), (x1, y1) in zip(table, table[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    (x0, y0), (x1, y1) = table[-2], table[-1]
    return max(1.0, y1 + (y1 - y0) * (x - x1) / (x1 - x0))


def t_read(table, L):
    """Seconds to read a prompt of L tokens cold."""
    return 0.0 if L <= 0 else L / interp(table, L)


def t_read_new(P, K, table=READ832):
    """Seconds to read the uncached tail [K, P) of a P-token prompt."""
    return max(0.0, t_read(table, P) - t_read(table, K))


def t_write(C, ctx):
    return 0.0 if C <= 0 else C / interp(WRITE, ctx)


def load(p):
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return None


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# ---------------------------------------------------------------- rendering (Qwen3.8 chat template, see header)

def _content(m):
    c = m.get("content")
    if c is None:
        return ""
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "".join(x.get("text", "") if isinstance(x, dict) else str(x) for x in c)
    return str(c)


def _cmd(tc):
    fn = tc.get("function") if isinstance(tc, dict) else None
    a = (fn or {}).get("arguments") if isinstance(fn, dict) else None
    try:
        d = json.loads(a) if isinstance(a, str) else (a or {})
        return "".join(f"<parameter={k}>\n{v if isinstance(v, str) else json.dumps(v)}\n</parameter>\n" for k, v in d.items())
    except Exception:
        return f"<parameter=command>\n{a}\n</parameter>\n"


def render(messages, preserve_thinking=True):
    """Return (text, list of (start offset, kind label)) for one call's messages."""
    lqi = len(messages) - 1
    for i in range(len(messages) - 1, -1, -1):
        m = messages[i]
        if m.get("role") == "user":
            c = _content(m).strip()
            if not (c.startswith("<tool_response>") and c.endswith("</tool_response>")):
                lqi = i
                break
    out, starts = [], []
    pos = 0
    for i, m in enumerate(messages):
        r = m.get("role")
        c = _content(m).strip()
        if r == "system":
            s = "<|im_start|>system\n" + c + "<|im_end|>\n"
        elif r == "user":
            s = "<|im_start|>user\n" + c + "<|im_end|>\n"
        elif r == "assistant":
            rc = (m.get("reasoning_content") or "").strip() if isinstance(m.get("reasoning_content"), str) else ""
            if preserve_thinking or i > lqi:
                s = "<|im_start|>assistant\n<think>\n" + rc + "\n</think>\n\n" + c
            else:
                s = "<|im_start|>assistant\n" + c
            for n, tc in enumerate(m.get("tool_calls") or []):
                lead = ("\n\n" if c else "") if n == 0 else "\n"
                s += lead + "<tool_call>\n<function=bash>\n" + _cmd(tc) + "</function>\n</tool_call>"
            s += "<|im_end|>\n"
        elif r == "tool":
            prev = messages[i - 1].get("role") if i else None
            s = ("<|im_start|>user" if prev != "tool" else "") + "\n<tool_response>\n" + c + "\n</tool_response>"
            nxt = messages[i + 1].get("role") if i + 1 < len(messages) else None
            if nxt != "tool":
                s += "<|im_end|>\n"
        else:
            s = "<|im_start|>" + str(r) + "\n" + c + "<|im_end|>\n"
        starts.append((pos, label(m)))
        out.append(s)
        pos += len(s)
    return "".join(out) + "<|im_start|>assistant\n<think>\n", starts


def label(m):
    r = m.get("role")
    c = _content(m)
    if r == "system":
        return "system"
    if r == "assistant":
        return "assistant"
    if c.startswith("[[PINNED STATE"):
        return "pinned-state"
    if c.startswith("CONTEXT BUDGET NUDGE") or c.startswith("(No tool call") or "[SYSTEM NOTICE" in c[:40]:
        return "notice"
    if re.match(r"@@ST\d+@@", c) or "GLOBAL STATE" in c[:200] or "===STATE===" in c:
        return "state-block"
    if c.startswith("[compacted]") or "summary" in c[:200].lower():
        return "summary/compacted"
    if re.search(r"ITEM \d+/\d+ \(", c) and len(c) > 4000:
        return ("tool" if r == "tool" else "user") + ":raw-batch"
    return "tool" if r == "tool" else "user"


def lcp(a, b):
    lo, hi = 0, min(len(a), len(b))
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if a[:mid] == b[:mid]:
            lo = mid
        else:
            hi = mid - 1
    return lo


G = 64


def chain(text):
    h, out = 0, []
    for i in range(0, len(text) - G + 1, G):
        h = zlib.crc32(text[i:i + G].encode("utf-8", "replace"), h)
        out.append(h)
    return out


def chain_lcp(ha, hb):
    lo, hi = 0, min(len(ha), len(hb))
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if ha[mid - 1] == hb[mid - 1]:
            lo = mid
        else:
            hi = mid - 1
    return lo * G


def fl(x):
    return max(0, int(x) // BLOCK * BLOCK)


# ---------------------------------------------------------------- server log

LOG_RE = re.compile(r"INFO (\d\d-\d\d \d\d:\d\d:\d\d) \[loggers\.py:\d+\] Engine 000: Avg prompt throughput: ([\d.]+) "
                    r"tokens/s, Avg generation throughput: ([\d.]+) tokens/s, Running: (\d+) reqs, Waiting: (\d+) reqs, "
                    r"GPU KV cache usage: ([\d.]+)%, Prefix cache hit rate: ([\d.]+)%")
SPEC_RE = re.compile(r"INFO (\d\d-\d\d \d\d:\d\d:\d\d) \[metrics\.py:\d+\] SpecDecoding metrics: Mean acceptance length: ([\d.]+)")


def log_lines(paths):
    for p in paths:
        if not os.path.exists(p):
            continue
        with open(p, errors="replace") as f:
            prev = None
            for ln in f:
                m = LOG_RE.search(ln)
                if m:
                    t = datetime.strptime("2026-" + m.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    dt = 10.0 if prev is None else min(30.0, max(1.0, (t - prev).total_seconds()))
                    prev = t
                    yield ("eng", t, dt, float(m.group(2)), float(m.group(3)), int(m.group(4)), float(m.group(6)))
                    continue
                m = SPEC_RE.search(ln)
                if m:
                    t = datetime.strptime("2026-" + m.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    yield ("spec", t, float(m.group(2)))


def log_window(paths, t0, t1):
    gen = prm = 0.0
    dec, acc = [], []
    for x in log_lines(paths):
        if not (t0 <= x[1] <= t1):
            continue
        if x[0] == "spec":
            acc.append(x[2])
            continue
        _, t, dt, p, g, run, kv = x
        gen += g * dt
        prm += p * dt
        if p == 0 and g > 0 and run >= 1:
            dec.append(g)
    dec.sort()
    acc.sort()
    med = lambda v: v[len(v) // 2] if v else None
    return {"log_gen_tokens": round(gen), "log_prompt_tokens": round(prm), "decode_only_intervals": len(dec),
            "decode_only_median_tok_s": med(dec), "decode_only_p90_tok_s": dec[int(0.9 * (len(dec) - 1))] if dec else None,
            "spec_mean_accept_len_median": med(acc)}


# ---------------------------------------------------------------- file operations (notes arms)

def item_sizes(task_dir):
    out = {}
    try:
        with open(os.path.join(task_dir, "environment", "stream.jsonl")) as f:
            for i, ln in enumerate(f, 1):
                out[i] = len(json.loads(ln)["text"].encode()) + 1
    except Exception:
        pass
    return out


HEREDOC = re.compile(r"cat\s*>\s*(\S+)\s*<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n(.*?)\n\2", re.S)


def file_ops(cmds, sizes):
    """Count and size the model's file operations from its commands (estimates; see the note)."""
    files, w_n, w_b, r_n, r_b = {}, 0, 0, 0, 0
    item = 0
    state_size = 0
    for c in cmds:
        for path, _, body in HEREDOC.findall(c):
            files[path] = len(body.encode()) + 1
            w_n += 1
            w_b += files[path]
        for m in re.finditer(r"\bnext\s*>\s*(\S+)", c):
            item += 1
            files[m.group(1).rstrip(";&")] = sizes.get(item, 0)
            w_n += 1
            w_b += sizes.get(item, 0)
        for m in re.finditer(r"apply\.py\s+(\S+)", c):
            p = m.group(1).rstrip(";&")
            b = files.get(p, 0)
            # apply.py reads the batch and state.json, rewrites state.json (~25 bytes per counter, ~160 counters)
            state_size = 160 * 25
            r_n += 2
            r_b += b + state_size
            w_n += 1
            w_b += state_size
        for m in re.finditer(r"\b(?:cat|head|tail|wc(?:\s+-\w+)?)\s+(/app/\S+)", c):
            p = m.group(1).rstrip(";&")
            if not re.search(r"cat\s*>", c[max(0, m.start() - 2):m.end()]):
                r_n += 1
                r_b += files.get(p, 0)
        if re.search(r"grep[^\n]*\*\.txt", c) or re.search(r"glob\.glob|for i in range\(1, ?2[01]\)", c):
            n_loop = max(1, len(re.findall(r"echo \"== ", c)) or 1)
            mm = re.search(r"for c in ([^;]+);", c)
            n_loop = len(mm.group(1).split()) if mm else 1
            batch = sum(v for k, v in files.items() if re.search(r"(batch|item)_\d+\.txt$", k))
            r_n += n_loop * sum(1 for k in files if re.search(r"(batch|item)_\d+\.txt$", k))
            r_b += n_loop * batch
        if re.search(r"open\(['\"]/app/notes/state\.json['\"]\)", c):
            r_n += 1
            r_b += state_size
        if "answers.json" in c and ("json.dump" in c or ">" in c):
            w_n += 1
            w_b += 24 * 20
    return {"file_writes": w_n, "bytes_written": w_b, "file_reads": r_n, "bytes_read": r_b,
            "files_created": len(files)}


# ---------------------------------------------------------------- one trial

def trial(tdir, logs, want_calls):
    agent = os.path.join(tdir, "agent")
    res = load(os.path.join(tdir, "result.json"))
    if not res or not res.get("finished_at"):
        return None
    cfg = load(os.path.join(tdir, "config.json")) or {}
    kw = (cfg.get("agent") or {}).get("kwargs") or {}
    u = load(os.path.join(agent, "usage.json")) or {}
    timing = load(os.path.join(agent, "timing.json")) or []
    sc = load(os.path.join(agent, "summary_calls.json")) or []
    imp = load(os.path.join(agent, "improved_stats.json")) or {}
    ctx = load(os.path.join(agent, "trajectory.ctx.json")) or {}
    steps = [s for seg in ctx.get("segments") or [] for s in seg.get("steps") or []
             if s.get("source") == "agent" and s.get("metrics")]
    ctx = None
    arm = os.path.basename(os.path.dirname(tdir)).split("__")[0]
    preserve = not (kw.get("drop_old_thinking") or imp.get("drop_old_thinking"))
    n_calls = int(u.get("n_lm_calls") or len(steps))

    ae = res.get("agent_execution") or {}
    t0, t1 = ts(ae.get("started_at") or res["started_at"]), ts(ae.get("finished_at") or res["finished_at"])
    wall = (ts(res["finished_at"]) - ts(res["started_at"])).total_seconds()
    agent_wall = (t1 - t0).total_seconds()
    llm_s = sum(float(x.get("llm_s") or 0) for x in timing if isinstance(x, dict))
    bash_s = sum(float(x.get("bash_s") or 0) for x in timing if isinstance(x, dict))
    llm_list = [float(x["llm_s"]) for x in timing if isinstance(x, dict) and "llm_s" in x]

    # completion split by characters
    th = vis = tool = 0
    for s in steps:
        th += len(s.get("reasoning_content") or "")
        vis += len(s.get("message") or "")
        for tc in s.get("tool_calls") or []:
            tool += len(str(tc.get("arguments") or ""))
    # thinking-dropped arms: the exported steps lose the old thinking; the harness logs what it dropped
    dt = os.path.join(agent, "dropped_thinking.jsonl")
    if os.path.exists(dt):
        with open(dt) as f:
            for ln in f:
                try:
                    th += int(json.loads(ln).get("chars") or 0)
                except Exception:
                    pass
    P = int(u.get("prompt_tokens") or 0)
    K = int(u.get("cached_tokens") or 0)
    C = int(u.get("completion_tokens") or 0)
    sP = sum(int(x.get("prompt_tokens") or 0) for x in sc)
    sK = sum(int(x.get("cached_tokens") or 0) for x in sc)
    sC = sum(int(x.get("completion_tokens") or 0) for x in sc)
    s_th = sum(a.get("reasoning_chars") or 0 for x in sc for a in x.get("attempts") or [])
    s_vis = sum(a.get("summary_chars") or 0 for x in sc for a in x.get("attempts") or [])
    per_call_complete = len(steps) >= n_calls - 1 and len(steps) > 0

    # reading-time estimate
    if per_call_complete:
        read_s = sum(t_read_new(int(s["metrics"]["prompt_tokens"]), int(s["metrics"].get("cached_tokens") or 0)) for s in steps)
        write_const_s = sum(t_write(int(s["metrics"]["completion_tokens"]),
                                    int(s["metrics"]["prompt_tokens"]) + int(s["metrics"]["completion_tokens"]) // 2) for s in steps)
        read_basis = "per call"
    else:
        avgP = P / max(1, n_calls)
        read_s = n_calls * t_read_new(avgP, K / max(1, n_calls))
        write_const_s = t_write(C, avgP)
        read_basis = "trial average (per-call usage missing)"
    # summary calls (C32): not timed by the harness; estimate from constants
    sum_read = sum(t_read_new(int(x.get("prompt_tokens") or 0), int(x.get("cached_tokens") or 0)) for x in sc)
    sum_write = sum(t_write(int(x.get("completion_tokens") or 0), int(x.get("prompt_tokens") or 0)) for x in sc)
    write_s = max(0.0, llm_s - read_s)
    other_s = agent_wall - llm_s - bash_s - (sum_read + sum_write)

    split_tok = {}
    tot_chars = th + vis + tool + s_th + s_vis
    if tot_chars:
        split_tok = {k: round((C + sC) * v / tot_chars) for k, v in
                     (("think", th + s_th), ("visible", vis + s_vis), ("tool_args", tool))}

    row = {
        "arm": arm, "seed": (re.search(r"-s(\d+)", tdir) or [None, None])[1], "calls": n_calls,
        "calls_with_usage": len(steps), "summary_calls": len(sc),
        "prompt_tokens": P + sP, "cached_tokens": K + sK, "new_tokens_read": P + sP - K - sK,
        "cached_share": round((K + sK) / (P + sP), 3) if P + sP else None,
        "completion_tokens": C + sC, "chars_think": th + s_th, "chars_visible": vis + s_vis, "chars_tool_args": tool,
        "completion_split_tokens": split_tok,
        "wall_s": round(wall), "agent_wall_s": round(agent_wall), "llm_s": round(llm_s), "tools_s": round(bash_s, 1),
        "est_read_s": round(read_s + sum_read), "est_write_s": round(write_s + sum_write),
        "summary_calls_est_s": round(sum_read + sum_write) if sc else 0,
        "other_s": round(other_s + (wall - agent_wall)), "read_basis": read_basis,
        "write_s_from_constants": round(write_const_s + sum_write),
        "implied_avg_write_tok_s": round((C + sC) / (write_s + sum_write), 1) if write_s + sum_write else None,
        "first_call_llm_s": llm_list[0] if llm_list else None,
        "preserve_thinking": preserve, "reward": ((res.get("verifier_result") or {}).get("rewards") or {}).get("reward"),
    }
    row.update(log_window(logs, t0, t1))

    if "notes" in tdir:
        task_dir = ((cfg.get("task") or {}).get("path")) or ""
        cmds = [str(x.get("cmd") or "") for x in timing if isinstance(x, dict) and "cmd" in x]
        row["file_ops"] = file_ops(cmds, item_sizes(task_dir))
        obs = 0
        for s in steps:
            o = s.get("observation")
            for r in (o or {}).get("results") or []:
                obs += len(str(r.get("content") or ""))
        row["file_ops"]["chars_of_command_output_shown_to_model"] = obs

    # ------------------------------------------------ Task B: reuse
    snaps = []
    for p in sorted(glob.glob(os.path.join(agent, "context_snapshots", "turn-*.json"))):
        d = load(p) or {}
        if d.get("final") or d.get("kind") in ("final", "summary"):
            continue
        snaps.append(p)
    reuse = None
    if per_call_complete and len(snaps) >= len(steps):
        reuse = reuse_census(snaps[:len(steps)], steps, preserve, want_calls)
    row["reuse"] = reuse if reuse else "not available (per-call usage or snapshot order incomplete)"
    if reuse and arm.startswith("A"):
        row["break_even"] = break_even(steps)
    return row


GEN_PROMPT = len("<|im_start|>assistant\n<think>\n")


def reuse_census(snap_paths, steps, preserve, want_calls):
    """Characters -> tokens: a shared prefix with call j is converted with call j's own ratio (server prompt tokens of
    j / rendered characters of j); a prefix that covers all of j's prompt is exactly T_j. Positions inside the current
    call use the current call's ratio. These are conversions, not tokenizations."""
    ratios = []
    prev_text, prev_starts, prev_msgs = None, None, None
    hashes, T, lens = [], [], []
    states = []                          # (pos, call index)
    calls = []
    for k, (p, s) in enumerate(zip(snap_paths, steps)):
        d = load(p)
        msgs = d["messages"]
        text, starts = render(msgs, preserve)
        Pk = int(s["metrics"]["prompt_tokens"])
        Kk = int(s["metrics"].get("cached_tokens") or 0)
        rk = Pk / max(1, len(text))
        ratios.append(len(text) / max(1, Pk))
        hk = chain(text)
        rec = {"call": k + 1, "prompt": Pk, "cached": Kk}

        def conv(lc, j):
            if lc >= lens[j] - GEN_PROMPT:
                return T[j]
            return round(lc * T[j] / max(1, lens[j]))

        if prev_text is None:
            rec.update(shared_prev=0, predicted=0, attn=0, break_at="first call", break_frac=0.0, layout_fix_new=Pk,
                       msgckpt_hit=0)
        else:
            L = lcp(prev_text, text)
            shared_prev = min(Pk, conv(L, k - 1))
            tok = lambda c: c * rk
            # best attention match over all earlier prompts
            l_j = []
            for j, hj in enumerate(hashes):
                lc = L if j == k - 1 else chain_lcp(hj, hk)
                l_j.append(min(Pk, conv(lc, j)))
            attn = max(fl(min(l, T[j])) for j, l in enumerate(l_j))
            usable = min(attn - BLOCK, fl(Pk - 1))
            hit = 0
            for pos, j in states:
                if pos <= usable and pos <= l_j[j] and pos > hit:
                    hit = pos
            # where the prefix with the previous call breaks
            idx = bisect.bisect_right([st for st, _ in starts], L) - 1
            pidx = bisect.bisect_right([st for st, _ in prev_starts], L) - 1
            if L >= len(prev_text) - len("<|im_start|>assistant\n<think>\n"):
                where = "append (previous prompt fully shared)"
            else:
                lab_prev = prev_starts[pidx][1] if pidx >= 0 else "?"
                lab_cur = starts[idx][1] if 0 <= idx < len(starts) else "end"
                cur_m = msgs[idx] if 0 <= idx < len(msgs) else None
                prev_m = prev_msgs[pidx] if 0 <= pidx < len(prev_msgs) else None
                kind = classify(prev_m, cur_m, lab_prev, lab_cur, len(prev_msgs), len(msgs), pidx)
                where = f"msg {pidx} of {len(prev_msgs)} ({lab_prev} -> {lab_cur}): {kind}"
            # L1: server keeps a state at every message start (no harness change)
            mstart = starts[idx][0] if 0 <= idx < len(starts) else L
            msgckpt = max(hit, min(fl(tok(mstart)) if mstart > 0 else 0, usable if usable > 0 else 0))
            # L2: append-only layout, state last: new = messages of this call whose text was not in the previous call
            prev_set = set(_content(m) + "\x00" + str(m.get("reasoning_content") or "") + json.dumps(m.get("tool_calls") or [])
                           for m in prev_msgs)
            new_chars = 0
            for i2, m in enumerate(msgs):
                key = _content(m) + "\x00" + str(m.get("reasoning_content") or "") + json.dumps(m.get("tool_calls") or [])
                if key not in prev_set:
                    e = starts[i2 + 1][0] if i2 + 1 < len(starts) else len(text)
                    new_chars += e - starts[i2][0]
            rec.update(shared_prev=shared_prev, predicted=hit, attn=attn, break_at=where,
                       break_frac=round(shared_prev / Pk, 3) if Pk else 0, msgckpt_hit=msgckpt,
                       layout_fix_new=min(Pk, round(rk * new_chars) + 2 * BLOCK))
            # junction
            if usable > hit:
                states += [(usable, k), (usable - BLOCK, k)]
        E = fl(Pk - 1)
        states += [(E, k), (E - BLOCK, k)]
        start_new = rec.get("predicted", 0)
        states += [(q, k) for q in range((start_new // RETAIN + 1) * RETAIN, Pk, RETAIN)]
        states = [(q, j) for q, j in states if q > 0]
        hashes.append(hk)
        T.append(Pk)
        lens.append(len(text))
        calls.append(rec)
        prev_text, prev_starts, prev_msgs = text, starts, msgs
        d = None

    P = sum(c["prompt"] for c in calls)
    K = sum(c["cached"] for c in calls)
    pred = sum(c["predicted"] for c in calls)
    sh = sum(c["shared_prev"] for c in calls)
    exact = sum(1 for c in calls if c["predicted"] == c["cached"])
    within = sum(1 for c in calls if abs(c["predicted"] - c["cached"]) <= BLOCK)
    # time: actual reading vs the two improvements
    rd = lambda key: sum(t_read_new(c["prompt"], c["prompt"] - min(c["prompt"], c[key])) for c in calls)
    actual_read = sum(t_read_new(c["prompt"], c["cached"]) for c in calls)
    l1_read = sum(t_read_new(c["prompt"], max(c["cached"], c["msgckpt_hit"])) for c in calls)
    l2_read = rd("layout_fix_new")
    breaks = {}
    for c in calls[1:]:
        key = re.sub(r"^msg \d+ of \d+ ", "", c["break_at"])
        e = breaks.setdefault(key, [0, 0, 0.0])
        e[0] += 1
        e[1] += c["prompt"] - c["cached"]
        # seconds this kind of break would save under the append-only layout (never negative)
        e[2] += max(0.0, t_read_new(c["prompt"], c["cached"])
                    - t_read_new(c["prompt"], c["prompt"] - min(c["prompt"], c["layout_fix_new"])))
    out = {
        "chars_per_token": {"min": round(min(ratios), 2), "median": round(sorted(ratios)[len(ratios) // 2], 2),
                            "max": round(max(ratios), 2)},
        "prompt": P, "shared_with_previous": sh, "predicted_reusable": pred, "actually_cached": K,
        "share_shared": round(sh / P, 3), "share_predicted": round(pred / P, 3), "share_cached": round(K / P, 3),
        "calls_predicted_exact": f"{exact}/{len(calls)}", "calls_within_1_block": f"{within}/{len(calls)}",
        "new_tokens_actual": P - K,
        "new_tokens_if_state_at_every_message_start": P - sum(max(c['cached'], c['msgckpt_hit']) for c in calls),
        "new_tokens_if_append_only_layout": sum(c["layout_fix_new"] for c in calls),
        "est_read_s_actual": round(actual_read), "est_read_s_msg_checkpoints": round(l1_read),
        "est_read_s_append_only": round(l2_read),
        "breaks": {k: {"calls": v[0], "new_tokens": v[1], "read_s_saved_if_append_only": round(v[2], 1)}
                   for k, v in sorted(breaks.items(), key=lambda kv: -kv[1][1])},
    }
    if want_calls:
        out["calls"] = calls
    return out


def classify(prev_m, cur_m, lab_prev, lab_cur, n_prev, n_cur, pidx):
    if cur_m is None or pidx >= n_cur:
        return "messages removed at the end (rollback / trim)"
    if prev_m is None:
        return "append"
    if prev_m.get("role") == "assistant" and cur_m.get("role") == "assistant" and _content(prev_m) == _content(cur_m):
        if (prev_m.get("reasoning_content") or "") != (cur_m.get("reasoning_content") or ""):
            return "earlier thinking dropped/changed"
        if json.dumps(prev_m.get("tool_calls") or []) == json.dumps(cur_m.get("tool_calls") or []):
            # same message, rendered differently: with preserve_thinking=false the template writes an empty
            # <think></think> only for assistant turns after the last real user message; a new user message
            # (state, nudge, notice) moves that point and strips the empty block from the turns before it
            return "empty-think flip (template, preserve_thinking=false)"
    if prev_m.get("role") == "assistant" and cur_m.get("role") == "assistant" and \
            bool(prev_m.get("tool_calls")) != bool(cur_m.get("tool_calls")):
        return "tool-call turn re-rendered as plain text (mirror sync)"
    if lab_prev == "notice" and pidx <= 4:
        return "notice near the top rewritten (rollback retry counter)"
    if lab_prev == "pinned-state":
        return "pinned state (shown last) replaced by new turns"
    if lab_prev == "notice":
        return "notice/nudge (at the end) removed or moved"
    if lab_prev.endswith("raw-batch") and not lab_cur.endswith("raw-batch"):
        return "raw batch deleted after folding"
    if lab_prev == "state-block" or lab_cur == "state-block":
        return "state block near the top rewritten"
    if lab_prev == "summary/compacted" or lab_cur == "summary/compacted" or n_cur < n_prev // 2:
        return "history replaced (summary / compaction)"
    if pidx <= 4:
        return "edit near the top"
    if prev_m.get("role") == "assistant" and cur_m.get("role") == "assistant" and \
            (bool(prev_m.get("tool_calls")) != bool(cur_m.get("tool_calls")) or _content(prev_m) != _content(cur_m)):
        return "earlier assistant turn rewritten (mirror sync)"
    if n_cur < n_prev:
        return "earlier turn deleted"
    return "earlier turn rewritten in place"


def break_even(steps):
    """Keep-everything arm: cache on (832-token cold pieces, reuse) vs cache off (4096-token pieces, read all)."""
    cum_on = cum_off = 0.0
    first = None
    rows = []
    for i, s in enumerate(steps, 1):
        Pk = int(s["metrics"]["prompt_tokens"])
        Kk = int(s["metrics"].get("cached_tokens") or 0)
        cum_on += t_read_new(Pk, Kk, READ832)
        cum_off += t_read(READ4096, Pk)
        if first is None and cum_on < cum_off:
            first = i
        rows.append((i, Pk, Kk, round(cum_on, 1), round(cum_off, 1)))
    p1 = int(steps[0]["metrics"]["prompt_tokens"])
    return {"calls": len(steps), "break_even_call": first, "read_s_cache_on": round(cum_on), "read_s_cache_off": round(cum_off),
            "first_call_penalty_s": round(t_read(READ832, p1) - t_read(READ4096, p1), 2),
            "cold_penalty_full_last_prompt_s": round(t_read(READ832, rows[-1][1]) - t_read(READ4096, rows[-1][1]), 1),
            "cumulative": rows}


def main():
    args = sys.argv[1:]
    want_calls = "--calls" in args
    runs, logs = [], []
    i = 0
    while i < len(args):
        if args[i] == "--runs":
            runs.append(args[i + 1]); i += 2
        elif args[i] == "--log":
            logs.append(args[i + 1]); i += 2
        else:
            i += 1
    runs = runs or DEFAULT_RUNS
    logs = logs or DEFAULT_LOGS
    rows = []
    for r in runs:
        for tdir in sorted(glob.glob(os.path.join(r, "*", "*__*"))):
            if not os.path.isdir(os.path.join(tdir, "agent")):
                continue
            row = trial(tdir, logs, want_calls)
            if row:
                rows.append(row)
                print("# done", row["arm"], row["seed"], file=sys.stderr)
    cols = ["arm", "seed", "calls", "prompt_tokens", "cached_tokens", "new_tokens_read", "completion_tokens", "wall_s",
            "est_write_s", "est_read_s", "tools_s", "summary_calls_est_s", "other_s", "implied_avg_write_tok_s",
            "decode_only_median_tok_s"]
    print("\t".join(cols))
    for r in rows:
        print("\t".join(str(r.get(c, "")) for c in cols))
    print("\narm\tseed\tthink_chars\tvisible_chars\ttool_arg_chars\tsplit_tokens(think/visible/tool, by chars)")
    for r in rows:
        print(f"{r['arm']}\t{r['seed']}\t{r['chars_think']}\t{r['chars_visible']}\t{r['chars_tool_args']}\t{r['completion_split_tokens']}")
    print("\narm\tseed\tshared_prev\tpredicted\tcached\tpred_exact\tpred_within_1blk\tread_s_actual\tread_s_msgckpt\tread_s_appendonly")
    for r in rows:
        x = r["reuse"]
        if isinstance(x, dict):
            print(f"{r['arm']}\t{r['seed']}\t{x['share_shared']}\t{x['share_predicted']}\t{x['share_cached']}\t"
                  f"{x['calls_predicted_exact']}\t{x['calls_within_1_block']}\t{x['est_read_s_actual']}\t"
                  f"{x['est_read_s_msg_checkpoints']}\t{x['est_read_s_append_only']}")
        else:
            print(f"{r['arm']}\t{r['seed']}\t{x}")
    print("\n" + json.dumps(rows, indent=1, default=str))


if __name__ == "__main__":
    main()
