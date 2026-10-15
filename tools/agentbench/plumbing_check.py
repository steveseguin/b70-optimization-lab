#!/usr/bin/env python3
"""plumbing_check.py WORKDIR: judge one plumbing-test.sh run (see that script). Prints one JSON object.

Reads WORKDIR/out/jobs/plumb-AGENT/trial/agent/requests.jsonl (the agent's own requests, full bodies, from the host
bridge), WORKDIR/fake-requests.jsonl (what the fake model received from ctxkeeper), the verifier's details.json, the
agent's exit.json and memory.json, and ctxkeeper's /ctxkeeper/status.
"""
import glob, json, os, re, subprocess, sys


def jl(p):
    try:
        return [json.loads(l) for l in open(p) if l.strip()]
    except OSError:
        return []


def load(p):
    try:
        return json.load(open(p))
    except (OSError, ValueError):
        return None


def text_of(m):
    c = m.get("content")
    if isinstance(c, list):
        c = "\n".join(str(p.get("text", "")) if isinstance(p, dict) else str(p) for p in c)
    return str(c or "")


def main():
    w = sys.argv[1]
    trial = glob.glob(os.path.join(w, "out/jobs/*/trial"))[0]
    agent = os.path.basename(os.path.normpath(w))
    tap = jl(os.path.join(trial, "agent/requests.jsonl"))
    fake = jl(os.path.join(w, "fake-requests.jsonl"))
    details = load(os.path.join(trial, "verifier/details.json")) or {}
    ab = load(os.path.join(trial, "agent/agentbench.json")) or {}
    hist = ab.get("history") or {}
    status = load(os.path.join(w, "ctxkeeper-status.json")) or {}
    exitj = ab.get("agent_exit") or {}
    mem = ab.get("memory") or {}

    chat = [r for r in tap if r.get("method") == "POST" and "/chat/completions" in r.get("path", "")]
    bodies = []
    for r in chat:
        try:
            bodies.append(json.loads(r.get("body") or "{}"))
        except ValueError:
            bodies.append({})
    main_key = hist.get("main_conversation")
    main = [b for r, b in zip(chat, bodies) if r.get("conv") == main_key]

    def first_req_with(pattern):
        for i, b in enumerate(main):
            for m in b.get("messages") or []:
                if m.get("role") not in ("system", "assistant") and re.search(pattern, text_of(m)):
                    return i
        return None

    fake_chat = [r["body"] for r in fake if r.get("method") == "POST" and "/chat/completions" in r.get("path", "")]
    fake_tools = [b for b in fake_chat if b.get("tools")]
    fake_ticket = any(re.search(r"TICKET 1/44", text_of(m)) for b in fake_chat for m in b.get("messages") or []
                      if m.get("role") not in ("system", "assistant"))
    shell_names = sorted({c["function"]["name"] for b in main for m in b.get("messages") or [] if m.get("role") == "assistant"
                          for c in m.get("tool_calls") or [] if isinstance(c, dict) and c.get("function")})
    last = main[-1] if main else {}
    head_text = "\n".join(text_of(m) for m in (last.get("messages") or [])[:(chat[-1].get("head") if chat else 0) or 0])
    prompt_in_head = "There is no room" not in head_text and "You maintain the Python library in /app/more_itertools" in head_text
    sys_chars = sum(len(text_of(m)) for m in (last.get("messages") or []) if m.get("role") in ("system", "developer"))
    tools_chars = len(json.dumps(last.get("tools") or []))
    sessions = {k: {"cuts": v.get("cuts"), "restarts": v.get("restarts"), "calls": v.get("upstream_calls")} for k, v in status.items()}
    def disk(img):          # the unpacked size `docker images` shows (inspect's .Size is the compressed store size)
        out = subprocess.run(["docker", "images", "--format", "{{.Size}}", img], capture_output=True, text=True).stdout.split()
        return out[0] if out else None
    size = disk(ab.get("image", ""))
    task_size = disk("agentbench-task:" + str(ab.get("task")))
    asst = [m for m in (last.get("messages") or []) if m.get("role") == "assistant"]
    toolm = [m for m in (last.get("messages") or []) if m.get("role") == "tool"]
    resend = {"assistant_keys": sorted({k for m in asst for k in m}),
              "resends_reasoning": any(m.get("reasoning_content") or m.get("reasoning") for m in asst),
              "tool_content_type": sorted({type(m.get("content")).__name__ for m in toolm}),
              "roles": "".join((m.get("role") or "?")[0] for m in (last.get("messages") or []))}
    res = {
        "agent": agent, "agent_version": ab.get("agent_version"), "image": ab.get("image"),
        "image_size": size, "task_image_size": task_size, "history_shape": resend,
        "checks": {
            "requests_reach_proxy_as_chat_completions": len(chat) >= 2 and hist.get("responses_api", 0) == 0,
            "requests_carry_tools": bool(hist.get("with_tools")),
            "no_chunked_bodies": hist.get("chunked_bodies", 0) == 0,
            "fake_model_received_tool_requests_via_ctxkeeper": len(fake_tools) >= 2,
            "next_ran_in_app": (details.get("tickets_fetched") or 0) >= 1,
            "ticket_text_came_back": first_req_with(r"TICKET 1/44") is not None and fake_ticket,
            "test_output_came_back": first_req_with(r"\bRan \d+ tests?\b|FAILED|\bOK\b") is not None,
            "second_ticket_came_back": first_req_with(r"TICKET 2/44") is not None,
            "agent_ended_by_itself": exitj.get("exit_code") == 0 and not exitj.get("timed_out"),
            "verifier_wrote_details": bool(details),
            "whole_history_every_request": bool(hist.get("whole_history_ok")),
            "one_ctxkeeper_conversation_no_restart": len([k for k, v in sessions.items() if (v["calls"] or 0) >= 3]) == 1
                                                     and not any(v.get("restarts") for v in sessions.values()),
        },
        "agent_requests": len(chat), "main_conversation_requests": len(main),
        "other_conversations": [c for c in hist.get("conversations", []) if c["key"] != main_key],
        "stream": hist.get("stream"), "tool_names_sent": hist.get("tool_names"), "shell_tool_used": shell_names,
        "task_prompt_in_ctxkeeper_head": prompt_in_head, "head_messages": chat[-1].get("head") if chat else None,
        "system_prompt_chars": sys_chars, "tools_schema_chars": tools_chars,
        "approx_fixed_tokens": round((sys_chars + tools_chars) / 3.6),
        "request_params": {k: v for k, v in last.items() if k not in ("messages", "tools")},
        "ctxkeeper_sessions": sessions, "agent_exit": exitj,
        "memory_mib": mem.get("mib"), "verifier": ab.get("verifier"),
    }
    if len(sys.argv) > 2 and sys.argv[2] == "slow":
        d0 = next((r["t"] for r in fake if r.get("delay_start")), None)
        d1 = next((r["t"] for r in fake if r.get("delay_end")), None)
        during = [r for r in tap if d0 and d1 and d0 < r.get("t", 0) < d1]
        res["checks"]["slow_reply_waited_without_retry"] = bool(d0 and d1) and not during
        res["delay_seconds"] = round(d1 - d0) if d0 and d1 else None
        res["requests_during_delay"] = len(during)
    if len(sys.argv) > 2 and sys.argv[2] == "stress":
        mreq = [r for r in chat if r.get("conv") == main_key]
        sizes = [r.get("bytes", 0) for r in mreq]
        grew = all(b >= a for a, b in zip(sizes, sizes[1:]))
        big = [v for v in status.values() if (v.get("upstream_calls") or 0) >= 3]
        res["checks"] = {
            "requests_reach_proxy_as_chat_completions": len(chat) >= 2 and hist.get("responses_api", 0) == 0,
            "no_chunked_bodies": hist.get("chunked_bodies", 0) == 0,
            "history_passed_4M_chars": max(sizes or [0]) >= 4_000_000,
            "history_never_shrank": grew,
            "whole_history_every_request": bool(hist.get("whole_history_ok")),
            "ctxkeeper_cut_without_restart": len(big) == 1 and (big[0].get("cuts") or 0) > 0 and not big[0].get("restarts"),
            "agent_ended_by_itself": exitj.get("exit_code") == 0 and not exitj.get("timed_out"),
            "verifier_wrote_details": bool(details),
        }
        res["main_requests"] = len(mreq)
        res["largest_request_bytes"] = max(sizes or [0])
        res["largest_request_messages"] = max((r.get("n_messages") or 0 for r in mreq), default=0)
        res["ctxkeeper"] = {k: {x: v.get(x) for x in ("cuts", "inplace_cuts", "restarts", "upstream_calls", "ratio")}
                            for k, v in status.items()}
    res["passed"] = all(res["checks"].values())
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
