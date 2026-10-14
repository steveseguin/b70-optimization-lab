#!/usr/bin/env python3
"""Replay FAp's recorded client trajectory through ctxkeeper with a mock upstream, capture every body the proxy
sends, and measure the prompt-prefix sharing between each notes call and the main call that preceded it.
Decisive offline test for the notes-path cache variance (XR4 84% vs XR6 2.2% cached)."""
import json, re, sys, tempfile
from pathlib import Path
sys.path.insert(0, "/home/steve/b70-optimization-lab/tools/ctxkeeper")
import ctxkeeper as ck

TRAJ = "/mnt/fast-ai/bench-results/context-longrun-20261012/client-repair2/runs/jobs/FAp__repair-n40-s2x/trial/agent/trajectory.json"
TOOL = {"type": "function", "function": {"name": "shell", "description": "Run a bash command in the task container.",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}}
NOTES_MARKERS = ("[[Message from the context keeper", "The turns mention these names", "Check these lines",
                 "Your reply did not use the layout")

traj = json.load(open(TRAJ))
ai_idx = [i for i, m in enumerate(traj) if m.get("role") == "assistant"]
print(f"trajectory: {len(traj)} messages, {len(ai_idx)} assistant turns", file=sys.stderr)


class Replay:
    def __init__(self):
        self.sent = []      # (kind, body)
        self.next_ai = 0

    def __call__(self, body):
        last = str(body["messages"][-1].get("content") or "")
        if last.startswith(NOTES_MARKERS):
            self.sent.append(("notes", body))
            return {"choices": [{"message": {"role": "assistant",
                                             "content": "NEW RULES\n(none)\nCHANGES\n(none)\nOPEN\n- keep going"},
                                 "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0}}
        self.sent.append(("main", body))
        msg = traj[ai_idx[self.next_ai]]
        self.next_ai += 1
        out = {"role": "assistant", "content": msg.get("content")}
        if msg.get("tool_calls"):
            out["tool_calls"] = msg["tool_calls"]
        fr = "tool_calls" if msg.get("tool_calls") else "stop"
        return {"choices": [{"message": out, "finish_reason": fr}], "usage": {"prompt_tokens": 0, "completion_tokens": 0}}


mock = Replay()
tmp = tempfile.TemporaryDirectory()
keeper = ck.Keeper(mock, Path(tmp.name), budget=32768, target_ratio=0.6, headroom=1024, reply_reserve=2048,
                   notes_thinking=False, max_recalls=16, notes_mode="inplace", inplace_tokens=15000,
                   notes_checks="off", recite_when=r"(?m)^TICKET \d+/\d+ \((BUG|NOTICE)\)")

for n, i in enumerate(ai_idx):
    body = {"model": "qwen38-27b-fp8", "messages": [dict(m) for m in traj[:i]], "max_tokens": 8192,
            "temperature": 0, "tools": [TOOL], "chat_template_kwargs": {"enable_thinking": True}}
    keeper.complete(body)
print(f"upstream calls: {len(mock.sent)} ({sum(1 for k, _ in mock.sent if k == 'notes')} notes)", file=sys.stderr)


def shared_prefix(a, b):
    """Messages equal as dicts, then a char-level match inside the first differing message."""
    n, chars = 0, 0
    for x, y in zip(a, b):
        if x != y:
            sx, sy = json.dumps(x, sort_keys=True), json.dumps(y, sort_keys=True)
            k = 0
            while k < min(len(sx), len(sy)) and sx[k] == sy[k]:
                k += 1
            return n, chars + k, (x, y)
        n += 1
        chars += len(json.dumps(x, sort_keys=True))
    return n, chars, None


last_main = None
print(f"{'call':>4} {'kind':>5} {'msgs':>5} {'shared_msgs':>11} {'shared_chars':>12} {'total_chars':>11} {'share%':>7}  first divergence")
for idx, (kind, body) in enumerate(mock.sent):
    if kind == "main":
        last_main = body["messages"]
        continue
    if last_main is None:
        continue
    nm, ch, div = shared_prefix(body["messages"], last_main)
    total = sum(len(json.dumps(m, sort_keys=True)) for m in body["messages"])
    where = ""
    if div:
        x, y = div
        dx = {k: (str(x.get(k))[:60], str(y.get(k))[:60]) for k in set(x) | set(y) if x.get(k) != y.get(k)}
        where = f"msg {nm} {x.get('role')}: " + "; ".join(f"{k}: notes={v[0]!r} main={v[1]!r}" for k, v in list(dx.items())[:2])
    print(f"{idx:>4} {kind:>5} {len(body['messages']):>5} {nm:>11} {ch:>12,} {total:>11,} {100*ch/max(total,1):>6.1f}%  {where}")
