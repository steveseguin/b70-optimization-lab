"""Control-flow test of KeeperAgent._keep_inplace and the chunked _keep without a model, docker or the harness loop:
the agent object is built without __init__, with a fake budget, sandbox and notes call."""
import asyncio, json, sys, types
sys.path.insert(0, "/mnt/fast-ai/src/context-language-models/clm"); sys.path.insert(0, ".")
import clm_keeper as ck

class Budget:
    strict_target = 30720
    def count(self, msgs): return sum(len(str(m.get("content") or "")) for m in msgs) // 4
class Env:
    def __init__(self): self.cmds = []
    async def exec(self, command, timeout_sec=0):
        self.cmds.append(command); return types.SimpleNamespace(return_code=0, stdout="")
def reply(text, finish="stop", cached=20000):
    msg = types.SimpleNamespace(content=text, tool_calls=None)
    usage = types.SimpleNamespace(prompt_tokens=25000, completion_tokens=200, prompt_tokens_details=types.SimpleNamespace(cached_tokens=cached))
    return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg, finish_reason=finish)], usage=usage)

def agent(replies, **over):
    a = object.__new__(ck.KeeperAgent)
    a.__dict__.update(_budget=Budget(), _protect=2, notes="", notes_mode="delta", notes_inplace=True, inplace_turn_tokens=300, inplace_turn_hold=0,
                      notes_max_tokens=2048, notes_chunk_tokens=400, _pin_tail="", n_inplace=0, n_inplace_failed=0, inplace_cached=0, inplace_prompt=0,
                      inplace_failures=[], n_items_archived=0, n_sums_corrected=0, n_delta_fallbacks=0, n_notes_failed=0, n_rules_put_back=0, n_lm_calls=7, n_inplace_redone=0,
                      _delivered={}, _mixed={}, n_not_archived_mixed=0, n_archive_failed=0, auto_retrieve=0, manage_calls=[], _server_total=0,
                      trigger_ratio=1.0, target_ratio=0.35, _largest_delivery=500, keep_headroom=100, notes_thinking=False, calls=[], snaps=[])
    a.__dict__.update(over)
    it = iter(replies)
    def notes_call(req, thinking=None, live=False):
        a.calls.append({"n": len(req), "live": live, "thinking": thinking, "last": req[-1]["content"][:60]})
        return next(it, None) or reply("(the fake ran out of replies)")
    a._notes_call = notes_call
    a._snap = lambda req, kind: a.snaps.append(kind)
    return a

def convo(n_items, ask_last=False):
    msgs = [{"role": "system", "content": "sys"}, {"role": "user", "content": "task"}]
    for i in range(1, n_items + 1):
        body = ("x went up by forty-nine. " * 20) + ("abcd12 was set to two hundred and ninety-four. It gained 12. " if i == 2 else "")
        kind = "PROBE" if ask_last and i == n_items else "UPDATE"
        text = f"ITEM {i}/9 ({kind})\n" + (body if kind == "UPDATE" else "PROBE: now.\nASK p1_1: What value does abcd12 hold now?") + "\n\n(exit_code=0)"
        msgs += [{"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "bash", "arguments": json.dumps({"command": "next"})}}]},
                 {"role": "tool", "content": text}]
    return msgs

async def main():
    # 1. the in-place cut is made: all turns go, the pin holds the notes and the continuity line
    a = agent([reply("NEW RULES\n(none)\nCHANGES\nabcd12: 294 + 12 = 307\nOPEN\n- continue with next")])
    a._delivered = {i: f"item {i} text" for i in range(1, 6)}
    env, msgs = Env(), convo(5)
    assert await a._keep_inplace(env, msgs, a._budget.count(msgs)) is True
    assert len(msgs) == 3 and msgs[2]["content"].startswith("[[NOTES kept by the harness: 5 earlier turns"), msgs[2]["content"][:80]
    assert "abcd12: 306" in a.notes and a.n_sums_corrected == 1, a.notes
    assert "'ITEM 5/9 (UPDATE)'" in msgs[2]["content"] and a.n_items_archived == 5 and len(env.cmds) == 5
    assert a.calls == [{"n": 13, "live": True, "thinking": False, "last": a.calls[0]["last"]}] and a.calls[0]["last"].startswith("[[Message from the harness")
    rec = a.manage_calls[-1]; assert rec["reason"] == "keep-inplace" and rec["cached"] == 20000 and rec["turns_dropped"] == 5, rec
    assert not ck.wants_thinking(msgs)
    print("1 ok:", {k: rec[k] for k in ("turns_dropped", "before", "after", "notes_tokens", "cached", "items_archived")})
    # 2. a question is open: no cut
    a = agent([]); msgs = convo(5, ask_last=True); n = len(msgs)
    assert await a._keep_inplace(Env(), msgs, a._budget.count(msgs)) is False and len(msgs) == n and not a.calls
    # 3. too little in view: no cut
    a = agent([], inplace_turn_tokens=10 ** 6); msgs = convo(5)
    assert await a._keep_inplace(Env(), msgs, 1) is False and not a.calls
    # 4. no layout twice: nothing changes, the failure is counted, and the same turns are not tried again
    a = agent([reply("I will continue."), reply("next"), reply("again no layout")]); msgs = convo(5); n = len(msgs)
    assert await a._keep_inplace(Env(), msgs, 1) is False and len(msgs) == n and a.notes == "" and a.n_inplace_failed == 1 and len(a.calls) == 3
    assert await a._keep_inplace(Env(), msgs, 1) is False and len(a.calls) == 3
    # 5. working from a value nobody stated: asked again from the start with thinking on; refused twice = nothing changes
    bad = "NEW RULES\n(none)\nCHANGES\nabcd12: 5 + 1 = 6\nabcd12: 77 + 1 = 78\nOPEN\n"
    a = agent([reply(bad), reply(bad)]); msgs = convo(5); n = len(msgs)
    assert await a._keep_inplace(Env(), msgs, 1) is False and len(msgs) == n and a.notes == "" and "starts from 77" in a.inplace_failures[0]["why"], a.inplace_failures
    assert [c["thinking"] for c in a.calls] == [False, True] and a.calls[1]["n"] == a.calls[0]["n"], a.calls
    a = agent([reply(bad), reply("NEW RULES\n(none)\nCHANGES\nabcd12: 294 + 12 = 306\nOPEN\n")]); msgs = convo(5)
    a._delivered = {i: f"item {i} text" for i in range(1, 6)}
    assert await a._keep_inplace(Env(), msgs, 1) is True and "abcd12: 306" in a.notes and a.n_inplace_redone == 1 and len(msgs) == 3
    # 5b. after a failure the ordinary cut releases the hold
    a = agent([reply("x"), reply("y"), reply("z"), reply("NEW RULES\n(none)\nCHANGES\n(none)\nOPEN\n")] + [reply("NEW RULES\n(none)\nCHANGES\n(none)\nOPEN\n")] * 6); msgs = convo(8)
    a._budget.strict_target = 1100; a._delivered = {i: f"item {i} text" for i in range(1, 9)}
    await a._keep(Env(), msgs)
    assert a.n_inplace_failed == 1 and a.manage_calls[-1]["reason"] == "keep" and a.inplace_turn_hold == 0, (a.n_inplace_failed, a.manage_calls[-1], a.inplace_turn_hold)
    # 6. the ordinary cut with pieces: two delta calls for one cut, then a second cut continues from the pin
    a = agent([reply("NEW RULES\n- R one\nCHANGES\nabcd12: 294\nOPEN\n"), reply("NEW RULES\n(none)\nCHANGES\nabcd12: 294 + 12 = 306\nOPEN\n"),
               reply("NEW RULES\n(none)\nCHANGES\n(none)\nOPEN\n")], notes_inplace=False)
    a._budget.strict_target = 1100
    a._delivered = {i: f"item {i} text" for i in range(1, 9)}
    msgs = convo(8); env = Env()
    await a._keep(env, msgs)
    rec = a.manage_calls[-1]
    assert rec["reason"] == "keep" and rec["notes_pieces"] >= 2 and "abcd12: 306" in a.notes and "R one" in a.notes, (rec, a.notes)
    assert msgs[2]["content"].startswith("[[NOTES kept") and msgs[-1]["role"] == "tool"
    print("6 ok:", {k: rec[k] for k in ("turns_dropped", "notes_pieces", "notes_attempts", "before", "after")}, "| calls", len(a.calls))
    print("ALL OK")
asyncio.run(main())
