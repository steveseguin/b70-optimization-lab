"""Rebuild LFM keeper requests from the c22b L1 state and compare: as-is vs an assistant prefill 'NEW RULES'."""
import json, sys, time, urllib.request
sys.path.insert(0, "/home/steve/b70-optimization-lab/tools/ctxkeeper")
import ctxkeeper as ck
d, task, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
arch = {a["n"]: a["message"] for a in map(json.loads, open(d + "archive.jsonl"))}
hist = [json.loads(l) for l in open(d + "notes-history.jsonl")]
opening = json.load(open(task))["messages"][:2]          # the agent's real opening, from a context snapshot
def ask(msgs):
    body = {"model": "lfm25-24b-a2b", "messages": msgs, "max_tokens": 6144, "temperature": 0, "thinking_budget_tokens": 0}
    t = time.monotonic()
    r = json.loads(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:18110/v1/chat/completions",
        json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=900).read())
    return r["choices"][0]["message"].get("content") or "", r["usage"]["completion_tokens"], time.monotonic() - t
rows = []
picks = [16, 19, 21]
for i in picks:
    lo, hi = hist[i]["upto"], hist[i + 1]["upto"]
    turns = [arch[k] for k in range(lo, hi) if k in arch]
    if not turns:
        continue
    text = ck.KEEPER_REQUEST.format(opening=ck.render_turns(opening), notes=hist[i]["notes"], still="",
                                    turns=ck.render_turns(turns, ids=True), overlap="")
    base = [{"role": "system", "content": ck.KEEPER_SYSTEM}, {"role": "user", "content": text}]
    for mode in ("prefill",):
        msgs = base + ([{"role": "assistant", "content": "NEW RULES\n"}] if mode == "prefill" else [])
        out, w, s = ask(msgs)
        full = ("NEW RULES\n" + out) if mode == "prefill" else out
        ok = full.lstrip().startswith("NEW RULES") and "CHANGES" in full and "<|tool_call" not in full
        rows.append(dict(i=i, turns=len(turns), mode=mode, layout_ok=ok, written=w, s=round(s, 1), head=out))
        print(json.dumps(rows[-1]), flush=True)
json.dump(rows, open(sys.argv[4], "w"), indent=1)
